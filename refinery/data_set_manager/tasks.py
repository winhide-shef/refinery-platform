from celery.schedules import crontab
from celery.task import task, periodic_task
from celery.task.sets import TaskSet, subtask
from collections import defaultdict
from core.models import *
from datetime import date, datetime, timedelta
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.db.utils import IntegrityError
from file_store.tasks import create, delete, read
from data_set_manager.models import Investigation, Study
from data_set_manager.isa_tab_parser import IsaTabParser
import csv, errno, ftplib, glob, os, os.path, re, shutil, socket, string
import subprocess, sys, tempfile, time, traceback, urllib2, traceback
from zipfile import ZipFile, BadZipfile


def create_dir(file_path):
    """
    Name: create_dir
    Description:
        creates a directory if it needs to be created
    Parameters:
        file_path: directory to create if necessary
    """
    try:
        os.makedirs(file_path)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise

@task()
def convert_to_isatab(accession):
    """
    Name: convert_to_isatab
    Description:
        converts MAGE-Tab file from ArrayExpress into ISA-Tab, zips up the 
        ISA-Tab, and zips up the MAGE-Tab
    Parameters:
        accession: ArrayExpress study to convert
    """
    retval = 1 #successful conversion
    command = "./convert.sh %s" % accession
    
    #send stdout and stderr to a unique temp directory to avoid console
    temp_dir = tempfile.mkdtemp()
    stderr_n = tempfile.NamedTemporaryFile(dir=temp_dir, prefix='ae_stderr').name
    stdout_n = tempfile.NamedTemporaryFile(dir=temp_dir, prefix='ae_stdout').name

    #create the subprocess
    process = subprocess.Popen(args=command, shell=True, 
                               cwd=settings.CONVERSION_DIR, 
                               stderr=open(stderr_n, 'wb'),
                               stdout=open(stdout_n, 'wb'))
    #run the subprocess and grab the exit code
    exit_code = process.wait()
    #process stderr
    stderr = open(stderr_n).read().strip()
    if stderr:
        #unsuccessful conversion, so remove the investigation file and dir
        shutil.rmtree(os.path.join(settings.ISA_TAB_DIR, accession))
        
        if exit_code != 0: #something bad happened
            shutil.rmtree(temp_dir)
            raise Exception, "Error Converting to ISA-Tab: %s" % stderr
        else:
            #print stderr
            retval = 0 #unsuccessful conversion, but clean exit
    else: #successfully converted
        #zip up ISA-Tab files 
        isatab_file_location = os.path.join(settings.ISA_TAB_DIR, 'isa', accession)
        preisatab_file_location = os.path.join(settings.ISA_TAB_DIR, 'preisa')
        """
        shutil makes a zip, tar, tar.gz, etc file out of files in given dir 
        Params:
        zip file prefix
        type of archive (e.g. zip, tar)
        superdirectory of the directory you want to archive
        name of directory that's being archived
        """ 
        shutil.make_archive(isatab_file_location, 'zip',  
                                        settings.ISA_TAB_DIR, accession)
        
        shutil.rmtree(temp_dir)
        
        #Get and zip up the MAGE-TAB and put in the ISA-Tab folder
        #make file name for ArrayExpress information to download into
        ae_name = tempfile.NamedTemporaryFile(dir=temp_dir, prefix='ae_').name
        #make url to fetch the experiment
        url = "%s/%s" % (settings.AE_BASE_URL, accession)
        
        #get ArrayExpress information to get URLs to download
        u = urllib2.urlopen(url)
        f = open(ae_name, 'wb')
        f.write(u.read()) #small file, so just grab whole thing in one go
        f.close()
        
        #open and read in the last line (the HTML) that has the info we want
        f = open(ae_name, 'rb')
        lines = f.readlines()
        f.close()
        last_line = lines[-1]
        
        #isolate the links by splitting on '<a href="'
        a_hrefs = string.split(last_line, '<a href="')
        #get the links we want
        for a_href in a_hrefs:
            if re.search(r'http://.+sdrf.txt', a_href) or re.search(r'http://.+idf.txt', a_href):
                link = string.split(a_href, '"').pop(0) #grab the link
                file_name = link.split('/')[-1] #get the file name
                
                #download and zip up locally because needs to be sequential
                dir_to_zip = os.path.join(temp_dir, accession)
                create_dir(dir_to_zip)
                
                u = urllib2.urlopen(link)
                file = os.path.join(dir_to_zip, file_name)
                f = open(file, 'wb')
                f.write(u.read()) #again, shouldn't be a large file
                f.close()
        
                #zip up and move the MAGE-TAB files
                shutil.make_archive(dir_to_zip, 'zip', temp_dir, 
                                                "MAGE-TAB_%s" % accession)
                shutil.move("%s.zip" % dir_to_zip, pre_isatab_file_location)

    #clean up the temporary directory and other files
    shutil.rmtree(temp_dir)

    return retval

"""
Name: get_arrayexpress_studies
Description:
    task that runs every Friday at 9:00PM that checks ArrayExpress for new
    and updated studies, then pulls down their metadata, converts it to
    ISA-Tab, and parses it into the Django database
"""
@periodic_task(run_every=crontab(hour="12", day_of_week="friday"))
def get_arrayexpress_studies():
    create_dir(settings.WGET_DIR) #make the directory if it's not there


@task() 
def create_dataset(investigation_uuid, username, public=False): 
    """get User for assigning DataSets"""
    user = User.objects.get(username__exact=username)
    if investigation_uuid != None:
        investigation = Investigation.objects.get(uuid=investigation_uuid)
        identifier = investigation.get_identifier()
    
        datasets = DataSet.objects.filter(name=identifier)
        if len(datasets): #if not 0, update dataset with new investigation
            """go through datasets until you find one with the correct owner"""
            for ds in datasets:
                own = ds.get_owner()
                if own == ae_user:
                    d = ds
                    break
            d.update_investigation(investigation, "updated %s" % date.today())
        else: #create a new dataset
            d = DataSet.objects.create(name=identifier)
            d.set_investigation(investigation)
            d.set_owner(user)
            if public:
                public_group = ExtendedGroup.objects.get(name__exact="Public")
                d.share(public_group)  

@task()
def parse_isatab(folder_name, isa_archive=None, pre_isa_archive=None):
    path = os.path.join(settings.ISA_TAB_DIR, folder_name)
    print path
    p = IsaTabParser()
    try:
        investigation = p.run(path, isa_archive, pre_isa_archive)
        return investigation.uuid
    except: #prints the error message without breaking things
        print "error: "
        exc_type, exc_value, exc_traceback = sys.exc_info()
        print "*** print_tb:"
        traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
        print "*** print_exception:"
        traceback.print_exception(exc_type, exc_value, exc_traceback,
                          limit=2, file=sys.stdout)
    return None

@task()
def process_isa_tab(uuid):
    ''' Unzip and parse ISA-Tab archive file object specified by UUID, return investigation UUID '''
    #TODO: check if the incoming ISA-Tab is already in the system
    result = read.delay(uuid)    #TODO: convert to subtask?
    item = result.get()
    input_file = item.datafile

    if input_file:
        # create folder for storing unzipped ISA-Tab contents (delete if it already exists)
        accession = os.path.splitext(os.path.basename(input_file.name))[0]
        extract_dir = os.path.join(settings.ISA_TAB_DIR, accession)
        if os.path.isdir(extract_dir):
            shutil.rmtree(extract_dir)
        os.mkdir(extract_dir)
    
        # unzip the ISA-Tab file (assumes there are no subfolders inside ISA-Tab archive)
        try:
            with ZipFile(input_file, 'r') as zf:
                zf.extractall(extract_dir)
        except BadZipfile as e:
            #TODO: write error msg to log
            print "Bad zipfile:", e
            return None

        # parse ISA-Tab
        p = IsaTabParser()
        investigation = p.run(extract_dir)  # takes "/full/path/to/isatab/zipfile/or/directory"
        return investigation.uuid
    else:
        return None