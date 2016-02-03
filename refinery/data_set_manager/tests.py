"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.http import QueryDict

from rest_framework.test import APIRequestFactory
from rest_framework.test import APITestCase
from rest_framework.test import APIClient

from .models import AttributeOrder, Assay, Study, Investigation
from .views import Assays, AssaysFiles, AssaysAttributes
from .utils import update_attribute_order_ranks, \
    customize_attribute_response, format_solr_response, get_owner_from_assay,\
    generate_facet_fields_query, hide_fields_from_weighted_list,\
    generate_filtered_facet_fields, generate_solr_params, \
    objectify_facet_field_counts
from .serializers import AttributeOrderSerializer
from core.models import DataSet, InvestigationLink


class AssaysAPITests(APITestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        investigation = Investigation.objects.create()
        study = Study.objects.create(file_name='test_filename123.txt',
                                     title='Study Title Test',
                                     investigation=investigation)

        assay = Assay.objects.create(
                study=study,
                measurement='transcription factor binding site',
                measurement_accession='http://www.testurl.org/testID',
                measurement_source='OBI',
                technology='nucleotide sequencing',
                technology_accession='test info',
                technology_source='test source',
                platform='Genome Analyzer II',
                file_name='test_assay_filename.txt',
                )
        self.valid_uuid = assay.uuid
        self.view = Assays.as_view()
        self.invalid_uuid = "0xxx000x-00xx-000x-xx00-x00x00x00x0x"
        self.invalid_format_uuid = "xxxxxxxx"

    def tearDown(self):
        Assay.objects.all().delete()
        Study.objects.all().delete()
        Investigation.objects.all().delete()

    def test_get(self):

        # valid_uuid
        uuid = self.valid_uuid
        request = self.factory.get('/api/v2/assays/%s/' % uuid)
        response = self.view(request, uuid)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
                response.content,
                '{"uuid":"%s",'
                '"study":"None: Study Title Test",'
                '"measurement":"transcription factor binding site",'
                '"measurement_accession":"http://www.testurl.org/testID",'
                '"measurement_source":"OBI",'
                '"technology":"nucleotide sequencing",'
                '"technology_accession":"test info",'
                '"technology_source":"test source",'
                '"platform":"Genome Analyzer II",'
                '"file_name":"test_assay_filename.txt"}'
                % uuid
                )
        # invalid_uuid
        uuid = self.invalid_uuid
        request = self.factory.get('/api/v2/assays/%s/' % uuid)
        response = self.view(request, uuid)
        response.render()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content, '{"detail":"Not found."}')

        # invalid_format_uuid
        uuid = self.invalid_format_uuid
        request = self.factory.get('/api/v2/assays/%s/' % uuid)
        response = self.view(request, uuid)
        response.render()
        self.assertEqual(response.status_code, 404)
        self.assertNotEqual(
                response.content,
                '{"uuid":"%s",'
                '"study":"None: Study Title Test",'
                '"measurement":"transcription factor binding site",'
                '"measurement_accession":"http://www.testurl.org/testID",'
                '"measurement_source":"OBI",'
                '"technology":"nucleotide sequencing",'
                '"technology_accession":"test info",'
                '"technology_source":"test source",'
                '"platform":"Genome Analyzer II",'
                '"file_name":"test_assay_filename.txt"}'
                % uuid)
        self.assertEqual(response.content, '{"detail":"Not found."}')


class AssaysFilesAPITests(APITestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        investigation = Investigation.objects.create()
        study = Study.objects.create(file_name='test_filename123.txt',
                                     title='Study Title Test',
                                     investigation=investigation)

        assay = Assay.objects.create(
                study=study,
                measurement='transcription factor binding site',
                measurement_accession='http://www.testurl.org/testID',
                measurement_source='OBI',
                technology='nucleotide sequencing',
                technology_accession='test info',
                technology_source='test source',
                platform='Genome Analyzer II',
                file_name='test_assay_filename.txt',
                )
        self.valid_uuid = assay.uuid
        self.view = AssaysFiles.as_view()
        self.invalid_uuid = "0xxx000x-00xx-000x-xx00-x00x00x00x0x"
        self.invalid_format_uuid = "xxxxxxxx"

    def tearDown(self):
        Assay.objects.all().delete()
        Study.objects.all().delete()
        Investigation.objects.all().delete()

    def test_get(self):
        # valid_uuid
        uuid = self.valid_uuid
        request = self.factory.get('/api/v2/assays/%s/files' % uuid)
        response = self.view(request, uuid)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content,
                         '{"facet_field_counts":{},'
                         '"attributes":null,'
                         '"nodes":[]}')

        # invalid_uuid
        uuid = self.invalid_uuid
        request = self.factory.get('/api/v2/assays/%s/files' % uuid)
        response = self.view(request, uuid)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content,
                         '{"facet_field_counts":{},'
                         '"attributes":null,'
                         '"nodes":[]}')

        # invalid_format_uuid
        uuid = self.invalid_format_uuid
        request = self.factory.get('/api/v2/assays/%s/files' % uuid)
        response = self.view(request, uuid)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content,
                         '{"facet_field_counts":{},'
                         '"attributes":null,'
                         '"nodes":[]}')


class AssaysAttributesAPITests(APITestCase):

    def setUp(self):
        self.user1 = User.objects.create_user("ownerJane", '', 'test1234')
        self.user2 = User.objects.create_user("guestName", '', 'test1234')
        self.user1.save()
        self.user2.save()
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.client.login(username='ownerJane', password='test1234')
        investigation = Investigation.objects.create()
        self.data_set = DataSet.objects.create(
                title="Test DataSet")
        InvestigationLink.objects.create(data_set=self.data_set,
                                         investigation=investigation)
        self.data_set.set_owner(self.user1)
        study = Study.objects.create(file_name='test_filename123.txt',
                                     title='Study Title Test',
                                     investigation=investigation)

        assay = Assay.objects.create(
                study=study,
                measurement='transcription factor binding site',
                measurement_accession='http://www.testurl.org/testID',
                measurement_source='OBI',
                technology='nucleotide sequencing',
                technology_accession='test info',
                technology_source='test source',
                platform='Genome Analyzer II',
                file_name='test_assay_filename.txt',
                )
        AttributeOrder.objects.create(
            study=study,
            assay=assay,
            solr_field='Character_Title',
            rank=1,
            is_exposed=True,
            is_facet=True,
            is_active=True,
            is_internal=False
        )
        AttributeOrder.objects.create(
            study=study,
            assay=assay,
            solr_field='Specimen',
            rank=2,
            is_exposed=True,
            is_facet=True,
            is_active=True,
            is_internal=False
        )
        AttributeOrder.objects.create(
            study=study,
            assay=assay,
            solr_field='Cell Type',
            rank=3,
            is_exposed=True,
            is_facet=True,
            is_active=True,
            is_internal=False
        )
        AttributeOrder.objects.create(
            study=study,
            assay=assay,
            solr_field='Analysis',
            rank=4,
            is_exposed=True,
            is_facet=True,
            is_active=True,
            is_internal=False
        )

        self.valid_uuid = assay.uuid
        self.view = AssaysAttributes.as_view()
        self.invalid_uuid = "0xxx000x-00xx-000x-xx00-x00x00x00x0x"
        self.invalid_format_uuid = "xxxxxxxx"
        self.client.logout()

    def tearDown(self):
        User.objects.all().delete()
        Assay.objects.all().delete()
        Study.objects.all().delete()
        Investigation.objects.all().delete()
        DataSet.objects.all().delete()
        AttributeOrder.objects.all().delete()

    def test_get(self):

        # valid_uuid
        uuid = self.valid_uuid
        request = self.factory.get('/api/v2/assays/%s/attributes' % uuid)
        response = self.view(request, uuid)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
                response.content,
                '[{"study":"None: Study Title Test",'
                '"assay":'
                '"Measurement: transcription factor binding site; '
                'Technology: nucleotide sequencing; '
                'Platform: Genome Analyzer II; '
                'File: test_assay_filename.txt",'
                '"solr_field":"Character_Title",'
                '"rank":"1",'
                '"is_exposed":true,'
                '"is_facet":true,'
                '"is_active":true,'
                '"is_internal":false,'
                '"id":1},'
                '{"study":"None: Study Title Test",'
                '"assay":'
                '"Measurement: transcription factor binding site; '
                'Technology: nucleotide sequencing; '
                'Platform: Genome Analyzer II; '
                'File: test_assay_filename.txt",'
                '"solr_field":"Specimen",'
                '"rank":"2",'
                '"is_exposed":true,'
                '"is_facet":true,'
                '"is_active":true,'
                '"is_internal":false,'
                '"id":2},'
                '{"study":"None: Study Title Test",'
                '"assay":'
                '"Measurement: transcription factor binding site; '
                'Technology: nucleotide sequencing; '
                'Platform: Genome Analyzer II; '
                'File: test_assay_filename.txt",'
                '"solr_field":"Cell Type",'
                '"rank":"3",'
                '"is_exposed":true,'
                '"is_facet":true,'
                '"is_active":true,'
                '"is_internal":false,'
                '"id":3},'
                '{"study":"None: Study Title Test",'
                '"assay":'
                '"Measurement: transcription factor binding site; '
                'Technology: nucleotide sequencing; '
                'Platform: Genome Analyzer II; '
                'File: test_assay_filename.txt",'
                '"solr_field":"Analysis",'
                '"rank":"4",'
                '"is_exposed":true,'
                '"is_facet":true,'
                '"is_active":true,'
                '"is_internal":false,'
                '"id":4}]'
                )

        # invalid uuid
        uuid = self.invalid_format_uuid
        request = self.factory.get('/api/v2/assays/%s/attributes' % uuid)
        response = self.view(request, uuid)
        response.render()
        self.assertEqual(response.status_code, 404)
        self.assertNotEqual(
                response.content,
                '[{"study":"None: Study Title Test",'
                '"assay":'
                '"Measurement: transcription factor binding site; '
                'Technology: nucleotide sequencing; '
                'Platform: Genome Analyzer II; '
                'File: test_assay_filename.txt",'
                '"solr_field":"Character_Title",'
                '"rank":"1",'
                '"is_exposed":true,'
                '"is_facet":true,'
                '"is_active":true,'
                '"is_internal":false,'
                '"id":1},'
                '{"study":"None: Study Title Test",'
                '"assay":'
                '"Measurement: transcription factor binding site; '
                'Technology: nucleotide sequencing; '
                'Platform: Genome Analyzer II; '
                'File: test_assay_filename.txt",'
                '"solr_field":"Specimen",'
                '"rank":"2",'
                '"is_exposed":true,'
                '"is_facet":true,'
                '"is_active":true,'
                '"is_internal":false,'
                '"id":2},'
                '{"study":"None: Study Title Test",'
                '"assay":'
                '"Measurement: transcription factor binding site; '
                'Technology: nucleotide sequencing; '
                'Platform: Genome Analyzer II; '
                'File: test_assay_filename.txt",'
                '"solr_field":"Cell Type",'
                '"rank":"3",'
                '"is_exposed":true,'
                '"is_facet":true,'
                '"is_active":true,'
                '"is_internal":false,'
                '"id":3},'
                '{"study":"None: Study Title Test",'
                '"assay":'
                '"Measurement: transcription factor binding site; '
                'Technology: nucleotide sequencing; '
                'Platform: Genome Analyzer II; '
                'File: test_assay_filename.txt",'
                '"solr_field":"Analysis",'
                '"rank":"4",'
                '"is_exposed":true,'
                '"is_facet":true,'
                '"is_active":true,'
                '"is_internal":false,'
                '"id":4}]'
                )
        self.assertEqual(response.content, '{"detail":"Not found."}')

        # invalid uuid
        uuid = ""
        request = self.factory.get('/api/v2/assays/%s/attributes' % uuid)
        response = self.view(request, uuid)
        response.render()
        self.assertEqual(response.status_code, 404)
        self.assertNotEqual(
                response.content,
                '[{"study":"None: Study Title Test",'
                '"assay":'
                '"Measurement: transcription factor binding site; '
                'Technology: nucleotide sequencing; '
                'Platform: Genome Analyzer II; '
                'File: test_assay_filename.txt",'
                '"solr_field":"Character_Title",'
                '"rank":"1",'
                '"is_exposed":true,'
                '"is_facet":true,'
                '"is_active":true,'
                '"is_internal":false,'
                '"id":1},'
                '{"study":"None: Study Title Test",'
                '"assay":'
                '"Measurement: transcription factor binding site; '
                'Technology: nucleotide sequencing; '
                'Platform: Genome Analyzer II; '
                'File: test_assay_filename.txt",'
                '"solr_field":"Specimen",'
                '"rank":"2",'
                '"is_exposed":true,'
                '"is_facet":true,'
                '"is_active":true,'
                '"is_internal":false,'
                '"id":2},'
                '{"study":"None: Study Title Test",'
                '"assay":'
                '"Measurement: transcription factor binding site; '
                'Technology: nucleotide sequencing; '
                'Platform: Genome Analyzer II; '
                'File: test_assay_filename.txt",'
                '"solr_field":"Cell Type",'
                '"rank":"3",'
                '"is_exposed":true,'
                '"is_facet":true,'
                '"is_active":true,'
                '"is_internal":false,'
                '"id":3},'
                '{"study":"None: Study Title Test",'
                '"assay":'
                '"Measurement: transcription factor binding site; '
                'Technology: nucleotide sequencing; '
                'Platform: Genome Analyzer II; '
                'File: test_assay_filename.txt",'
                '"solr_field":"Analysis",'
                '"rank":"4",'
                '"is_exposed":true,'
                '"is_facet":true,'
                '"is_active":true,'
                '"is_internal":false,'
                '"id":4}]'
                )
        self.assertEqual(response.content, '{"detail":"Not found."}')

    def test_put(self):

        # valid_uuid
        self.client.login(username='ownerJane', password='test1234')
        uuid = self.valid_uuid
        updated_attribute_1 = {'solr_field': 'Character_Title',
                               'rank': '3',
                               'is_exposed': 'False',
                               'is_facet': 'False',
                               'is_active': 'False'}
        updated_attribute_2 = {'id': '6',
                               'rank': '1',
                               'is_exposed': 'False',
                               'is_facet': 'False',
                               'is_active': 'False'}
        updated_attribute_3 = {'solr_field': 'Cell Type',
                               'rank': '4',
                               'is_exposed': 'False',
                               'is_facet': 'False',
                               'is_active': 'False'}
        updated_attribute_4 = {'solr_field': 'Analysis',
                               'id': '8',
                               'rank': '2',
                               'is_exposed': 'False',
                               'is_facet': 'False',
                               'is_active': 'False'}
        # Api client needs url to end / or it will redirect

        # update with solr_title
        response = self.client.put('/api/v2/assays/%s/attributes/' % uuid,
                                   updated_attribute_1)
        response.render()
        self.assertEqual(response.status_code, 202)
        self.assertNotEqual(
                response.content,
                '{"study":"None: Study Title Test",'
                '"assay":'
                '"Measurement: transcription factor binding site; '
                'Technology: nucleotide sequencing; '
                'Platform: Genome Analyzer II; '
                'File: test_assay_filename.txt",'
                '"solr_field":"Character_Title",'
                '"rank":"3",'
                '"is_exposed":true,'
                '"is_facet":true,'
                '"is_active":true,'
                '"is_internal":true,'
                '"id":5}'
                )
        self.assertEqual(
                response.content,
                '{"study":"None: Study Title Test",'
                '"assay":'
                '"Measurement: transcription factor binding site; '
                'Technology: nucleotide sequencing; '
                'Platform: Genome Analyzer II; '
                'File: test_assay_filename.txt",'
                '"solr_field":"Character_Title",'
                '"rank":"3",'
                '"is_exposed":false,'
                '"is_facet":false,'
                '"is_active":false,'
                '"is_internal":false,'
                '"id":5}'
                )

        # Update with attribute_order id
        response = self.client.put('/api/v2/assays/%s/attributes/' % uuid,
                                   updated_attribute_2)
        response.render()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(
                response.content,
                '{"study":"None: Study Title Test",'
                '"assay":'
                '"Measurement: transcription factor binding site; '
                'Technology: nucleotide sequencing; '
                'Platform: Genome Analyzer II; '
                'File: test_assay_filename.txt",'
                '"solr_field":"Specimen",'
                '"rank":"1",'
                '"is_exposed":false,'
                '"is_facet":false,'
                '"is_active":false,'
                '"is_internal":false,'
                '"id":6}'
                )

        # Invalid objects
        response = self.client.put('/api/v2/assays/%s/attributes/' % uuid,
                                   {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
                response.content, '"Requires attribute id or solr_field name."'
                )
        self.client.logout()

        # Invalid Login
        self.client.login(username='guestName', password='test1234')
        response = self.client.put('/api/v2/assays/%s/attributes/' % uuid,
                                   updated_attribute_3)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
                response.content, '"Only owner may edit attribute order."'
                )

        self.client.logout()


class UtilitiesTest(TestCase):

    def setUp(self):
        self.user1 = User.objects.create_user("ownerJane", '', 'test1234')
        self.user1.save()
        investigation = Investigation.objects.create()
        data_set = DataSet.objects.create(
                title="Test DataSet")
        InvestigationLink.objects.create(data_set=data_set,
                                         investigation=investigation)
        data_set.set_owner(self.user1)
        study = Study.objects.create(file_name='test_filename123.txt',
                                     title='Study Title Test',
                                     investigation=investigation)
        self.assay = Assay.objects.create(
                study=study,
                measurement='transcription factor binding site',
                measurement_accession='http://www.testurl.org/testID',
                measurement_source='OBI',
                technology='nucleotide sequencing',
                technology_accession='test info',
                technology_source='test source',
                platform='Genome Analyzer II',
                file_name='test_assay_filename.txt',
                )
        AttributeOrder.objects.create(
            study=study,
            assay=self.assay,
            solr_field='Character_Title',
            rank=1,
            is_exposed=True,
            is_facet=True,
            is_active=True,
            is_internal=False
        )
        AttributeOrder.objects.create(
            study=study,
            assay=self.assay,
            solr_field='Specimen',
            rank=2,
            is_exposed=True,
            is_facet=True,
            is_active=True,
            is_internal=False
        )
        AttributeOrder.objects.create(
            study=study,
            assay=self.assay,
            solr_field='Cell Type',
            rank=3,
            is_exposed=True,
            is_facet=True,
            is_active=True,
            is_internal=False
        )
        AttributeOrder.objects.create(
            study=study,
            assay=self.assay,
            solr_field='Analysis',
            rank=4,
            is_exposed=True,
            is_facet=True,
            is_active=True,
            is_internal=False
        )
        AttributeOrder.objects.create(
            study=study,
            assay=self.assay,
            solr_field='Organism',
            rank=5,
            is_exposed=True,
            is_facet=True,
            is_active=True,
            is_internal=False
        )
        AttributeOrder.objects.create(
            study=study,
            assay=self.assay,
            solr_field='Cell Line',
            rank=6,
            is_exposed=True,
            is_facet=True,
            is_active=True,
            is_internal=False
        )
        AttributeOrder.objects.create(
            study=study,
            assay=self.assay,
            solr_field='Type',
            rank=7,
            is_exposed=True,
            is_facet=True,
            is_active=True,
            is_internal=False
        )
        AttributeOrder.objects.create(
            study=study,
            assay=self.assay,
            solr_field='Group Name',
            rank=8,
            is_exposed=True,
            is_facet=True,
            is_active=True,
            is_internal=False
        )
        AttributeOrder.objects.create(
            study=study,
            assay=self.assay,
            solr_field='Gene',
            rank=9,
            is_exposed=False,
            is_facet=False,
            is_active=True,
            is_internal=False
        )
        AttributeOrder.objects.create(
            study=study,
            assay=self.assay,
            solr_field='Replicate Id',
            rank=10,
            is_exposed=False,
            is_facet=False,
            is_active=True,
            is_internal=False
        )
        AttributeOrder.objects.create(
            study=study,
            assay=self.assay,
            solr_field='Organism Part',
            rank=0,
            is_exposed=False,
            is_facet=False,
            is_active=True,
            is_internal=False
        )
        AttributeOrder.objects.create(
            study=study,
            assay=self.assay,
            solr_field='Name',
            rank=0,
            is_exposed=False,
            is_facet=False,
            is_active=True,
            is_internal=False
        )
        self.valid_uuid = self.assay.uuid
        self.invalid_uuid = 'xxxxxxxx'

    def tearDown(self):
        User.objects.all().delete()
        Assay.objects.all().delete()
        Study.objects.all().delete()
        Investigation.objects.all().delete()
        DataSet.objects.all().delete()
        InvestigationLink.objects.all().delete()
        AttributeOrder.objects.all().delete()

    def test_objectify_facet_field_counts(self):
        facet_field_array = {'WORKFLOW': ['1_test_04', 1,
                                          'output_file', 60,
                                          '1_test_02', 1],
                             'ANALYSIS': ['5dd6d3c3', 5,
                                          '08fc3964', 2,
                                          '0907a312', 1,
                                          '276adefd', 3,
                                          '2d761e26', 1,
                                          'b624d225', 5,
                                          '7ce99c97', 1,
                                          'bcc1644a', 5,
                                          '5499cc41', 5],
                             'Author': ['Vezza', 10,
                                        'Harslem/Heafner', 4,
                                        'McConnell', 5,
                                        'Vezza + Crocker', 2,
                                        'Crocker', 28],
                             'Year': ['1971', 54],
                             'SUBANALYSIS': ['1', 8, '2', 2, '-1', 9],
                             'TYPE': ['Derived Data File', 105,
                                      'Raw Data File', 9]}

        facet_field_obj = objectify_facet_field_counts(facet_field_array)
        self.assertDictEqual(facet_field_obj,
                        {'WORKFLOW': {'1_test_04': 1,
                                          'output_file': 60,
                                          '1_test_02': 1},
                             'ANALYSIS': {'5dd6d3c3': 5,
                                          '08fc3964': 2,
                                          '0907a312': 1,
                                          '276adefd': 3,
                                          '2d761e26': 1,
                                          'b624d225': 5,
                                          '7ce99c97': 1,
                                          'bcc1644a': 5,
                                          '5499cc41': 5},
                             'Author': {'Vezza': 10,
                                        'Harslem/Heafner': 4,
                                        'McConnell': 5,
                                        'Vezza + Crocker': 2,
                                        'Crocker': 28},
                             'Year': {'1971': 54},
                             'SUBANALYSIS': {'1': 8, '2': 2, '-1': 9},
                             'TYPE': {'Derived Data File': 105,
                                      'Raw Data File': 9}})

    def test_hide_fields_from_weighted_list(self):
        weighted_list = [(0, {'solr_field': 'uuid'}),
                         (0, {'solr_field': 'is_annotation'}),
                         (2, {'solr_field': 'genome_build'}),
                         (3, {'solr_field': 'django_ct'}),
                         (6, {'solr_field': 'django_id'}),
                         (7, {'solr_field': 'species'}),
                         (8, {'solr_field': 'file_uuid'}),
                         (12, {'solr_field': 'study_uuid'}),
                         (11, {'solr_field': 'assay_uuid'}),
                         (10, {'solr_field': 'type'}),
                         (9, {'solr_field': 'id'}),
                         (1, {'solr_field': 'name'}),
                         (4, {'solr_field': 'SubAnalysis'})]

        filtered_list = hide_fields_from_weighted_list(weighted_list)
        self.assertListEqual(filtered_list, ['SubAnalysis'])

    def test_generate_solr_params(self):
        # empty params
        query = generate_solr_params(QueryDict({}), self.valid_uuid)
        self.assertEqual(str(query),
                         'fq=assay_uuid%3A{}'
                         '&facet.field=Character_Title&'
                         'facet.field=Specimen&facet.field=Cell Type&'
                         'facet.field=Analysis&facet.field=Organism&'
                         'facet.field=Cell Line&facet.field=Type&'
                         'facet.field=Group Name&fl=Character_Title%2C'
                         'Specimen%2CCell Type%2CAnalysis%2COrganism%2C'
                         'Cell Line%2CType%2CGroup Name&'
                         'fq=type%3A%28%22Raw Data File%22 OR %22'
                         'Derived Data File%22 OR %22Array Data File'
                         '%22 OR %22Derived Array Data File%22 OR %22'
                         'Array Data Matrix File%22 OR%22Derived Array '
                         'Data Matrix File%22%29&fq=is_annotation%3A'
                         'false&start=0&rows=20&q=django_ct%3A'
                         'data_set_manager.node&wt=json&facet=true&'
                         'facet.limit=-1&facet.mincount=1'.format(
                                 self.valid_uuid))
        # added parameter
        parameter_dict = {'limit': 7, 'start': 2,
                          'include_facet_count': 'true',
                          'attributes': 'cats,mouse,dog,horse',
                          'facets': 'cats,mouse,dog,horse',
                          'pivots': 'cats,mouse',
                          'is_annotation': 'true'}
        parameter_qdict = QueryDict('', mutable=True)
        parameter_qdict.update(parameter_dict)
        query = generate_solr_params(parameter_qdict, self.valid_uuid)
        self.assertEqual(str(query),
                         'fq=assay_uuid%3A{}'
                         '&facet.field=cats&'
                         'facet.field=mouse&facet.field=dog&'
                         'facet.field=horse&fl=cats%2C'
                         'mouse%2Cdog%2Chorse&facet.pivot=cats%2Cmouse&'
                         'fq=type%3A%28%22Raw Data File%22 OR %22'
                         'Derived Data File%22 OR %22Array Data File'
                         '%22 OR %22Derived Array Data File%22 OR %22'
                         'Array Data Matrix File%22 OR%22Derived Array '
                         'Data Matrix File%22%29&fq=is_annotation%3A'
                         'true&start=2&rows=7&q=django_ct%3A'
                         'data_set_manager.node&wt=json&facet=true&'
                         'facet.limit=-1&facet.mincount=1'.format(
                                 self.valid_uuid))

    def test_generate_filtered_facet_fields(self):
        attribute_orders = AttributeOrder.objects.filter(
                assay__uuid=self.valid_uuid)
        attributes = AttributeOrderSerializer(attribute_orders, many=True)
        filtered = generate_filtered_facet_fields(attributes.data)
        self.assertListEqual(filtered, ['Character_Title', 'Specimen',
                                        'Cell Type', 'Analysis',
                                        'Organism', 'Cell Line',
                                        'Type', 'Group Name'])

    def test_generate_facet_fields_query(self):
        facet_field_string = ['REFINERY_SUBANALYSIS_6_3_s',
                              'REFINERY_WORKFLOW_OUTPUT_6_3_s',
                              'REFINERY_ANALYSIS_UUID_6_3_s',
                              'Author_Characteristics_6_3_s',
                              'Year_Characteristics_6_3_s']

        str_query = generate_facet_fields_query(facet_field_string)
        self.assertEqual(str_query,
                         '&facet.field=REFINERY_SUBANALYSIS_6_3_s'
                         '&facet.field=REFINERY_WORKFLOW_OUTPUT_6_3_s'
                         '&facet.field=REFINERY_ANALYSIS_UUID_6_3_s'
                         '&facet.field=Author_Characteristics_6_3_s'
                         '&facet.field=Year_Characteristics_6_3_s')

    def test_get_owner_from_assay(self):
        owner = get_owner_from_assay(self.valid_uuid).username
        # valid owner with valid uuid
        self.assertEqual(str(owner), 'ownerJane')

        # invalid uuid
        response = get_owner_from_assay(self.invalid_uuid)
        self.assertEqual(response, 'Error: Invalid uuid')

    def test_format_solr_response(self):

        # valid input
        solr_response = '{"responseHeader":{"status": 0, "params":' \
                        '{"facet": "true", "facet.mincount": "1",' \
                        '"start": "0",'\
                        '"q": "django_ct:data_set_manager.node",'\
                        '"facet.limit": "-1",'\
                        '"facet.field":'\
                        '["REFINERY_TYPE_6_3_s",'\
                        '"REFINERY_SUBANALYSIS_6_3_s",'\
                        '"REFINERY_WORKFLOW_OUTPUT_6_3_s",'\
                        '"REFINERY_ANALYSIS_UUID_6_3_s",'\
                        '"Author_Characteristics_6_3_s",'\
                        '"Year_Characteristics_6_3_s"],'\
                        '"wt": "json", "rows": "20"}},'\
                        '"response": {'\
                        '"numFound": 1, "start": 0,'\
                        '"docs": ['\
                        '{"Author_Characteristics_6_3_s": "Crocker",'\
                        '"REFINERY_ANALYSIS_UUID_6_3_s": "N/A",'\
                        '"REFINERY_WORKFLOW_OUTPUT_6_3_s": "N/A",'\
                        '"REFINERY_SUBANALYSIS_6_3_s": "-1",'\
                        '"Year_Characteristics_6_3_s": "1971",'\
                        '"REFINERY_TYPE_6_3_s": "Raw Data File"}]},'\
                        '"facet_counts": {"facet_queries": {},'\
                        '"facet_fields": {'\
                        '"REFINERY_TYPE_6_3_s":'\
                        '["Derived Data File", 105,'\
                        '"Raw Data File", 9],'\
                        '"REFINERY_SUBANALYSIS_6_3_s":'\
                        '["-1", 9, "0", 95, "1", 8, "2", 2]},'\
                        '"facet_dates": {}, "facet_ranges": {},'\
                        '"facet_intervals": {}, "facet_heatmaps": {}}}'

        formatted_response = format_solr_response(solr_response)
        self.assertDictEqual(
                formatted_response,
                {
                    'facet_field_counts':
                         {u'REFINERY_SUBANALYSIS_6_3_s':
                              {u'1': 8, u'0': 95, u'2': 2, u'-1': 9},
                          u'REFINERY_TYPE_6_3_s':
                              {u'Derived Data File': 105,
                               u'Raw Data File': 9}},
                     'attributes': [{
                         'attribute_type': 'Internal',
                         'display_name': u'Type',
                         'data_type': u's',
                         'internal_name': u'REFINERY_TYPE_6_3_s'},
                         {'attribute_type': 'Internal',
                          'display_name': 'Analysis Group',
                          'data_type': u's',
                          'internal_name': u'REFINERY_SUBANALYSIS_6_3_s'},
                         {'attribute_type': 'Internal',
                          'display_name': 'Output Type',
                          'data_type': u's',
                          'internal_name': u'REFINERY_WORKFLOW_OUTPUT_6_3_s'},
                         {'attribute_type': 'Internal',
                          'display_name': u'Analysis',
                          'data_type': u's',
                          'internal_name': u'REFINERY_ANALYSIS_UUID_6_3_s'},
                         {'attribute_type': 'Characteristics',
                          'display_name': u'Author',
                          'data_type': u's',
                          'internal_name': u'Author_Characteristics_6_3_s'},
                         {'attribute_type': 'Characteristics',
                          'display_name': u'Year',
                          'data_type': u's',
                          'internal_name': u'Year_Characteristics_6_3_s'}],
                     'nodes': [{
                         u'REFINERY_WORKFLOW_OUTPUT_6_3_s': u'N/A',
                         u'REFINERY_ANALYSIS_UUID_6_3_s': u'N/A',
                         u'Author_Characteristics_6_3_s': u'Crocker',
                         u'Year_Characteristics_6_3_s': u'1971',
                         u'REFINERY_SUBANALYSIS_6_3_s': u'-1',
                         u'REFINERY_TYPE_6_3_s': u'Raw Data File'}]
                }
        )

        # invalid input
        solr_response = {"test_object": "not a string"}
        error = format_solr_response(solr_response)
        self.assertEqual(error, "Error loading json.")

    def test_customize_attribute_response(self):
        attributes = ['REFINERY_FILETYPE_6_3_s',
                      'Title_Characteristics_6_3_s',
                      'REFINERY_TYPE_6_3_s',
                      'REFINERY_SUBANALYSIS_6_3_s',
                      'Month_Characteristics_6_3_s',
                      'REFINERY_NAME_6_3_s',
                      'REFINERY_WORKFLOW_OUTPUT_6_3_s',
                      'REFINERY_ANALYSIS_UUID_6_3_s',
                      'Author_Characteristics_6_3_s',
                      'Year_Characteristics_6_3_s']

        prettified_attributes = customize_attribute_response(attributes)
        self.assertListEqual(
                prettified_attributes,
                [{'data_type': 's',
                  'attribute_type': 'Internal',
                  'display_name': 'File Type',
                  'internal_name': 'REFINERY_FILETYPE_6_3_s'},
                 {'data_type': 's',
                  'attribute_type': 'Characteristics',
                  'display_name': 'Title',
                  'internal_name': 'Title_Characteristics_6_3_s'},
                 {'data_type': 's',
                  'attribute_type': 'Internal',
                  'display_name': 'Type',
                  'internal_name': 'REFINERY_TYPE_6_3_s'},
                 {'data_type': 's',
                  'attribute_type': 'Internal',
                  'display_name': 'Analysis Group',
                  'internal_name': 'REFINERY_SUBANALYSIS_6_3_s'},
                 {'data_type': 's',
                  'attribute_type': 'Characteristics',
                  'display_name': 'Month',
                  'internal_name': 'Month_Characteristics_6_3_s'},
                 {'data_type': 's',
                  'attribute_type': 'Internal',
                  'display_name': 'Name',
                  'internal_name': 'REFINERY_NAME_6_3_s'},
                 {'data_type': 's',
                  'attribute_type': 'Internal',
                  'display_name': 'Output Type',
                  'internal_name': 'REFINERY_WORKFLOW_OUTPUT_6_3_s'},
                 {'data_type': 's',
                  'attribute_type': 'Internal',
                  'display_name': 'Analysis',
                  'internal_name': 'REFINERY_ANALYSIS_UUID_6_3_s'},
                 {'data_type': 's',
                  'attribute_type': 'Characteristics',
                  'display_name': 'Author',
                  'internal_name': 'Author_Characteristics_6_3_s'},
                 {'data_type': 's',
                  'attribute_type': 'Characteristics',
                  'display_name': 'Year',
                  'internal_name': 'Year_Characteristics_6_3_s'}])

        attributes = ['treatment_Factor_Value_22_11_s',
                      'treatment_Characteristics_22_11_s',
                      'REFINERY_NAME_22_11_s',
                      'strain_Characteristics_22_11_s',
                      'organism_Characteristics_22_11_s',
                      'REFINERY_WORKFLOW_OUTPUT_22_11_s',
                      'Replicate_Id_Comment_22_11_s',
                      'REFINERY_ANALYSIS_UUID_22_11_s',
                      'REFINERY_FILETYPE_22_11_s',
                      'cell_line_Factor_Value_22_11_s',
                      'cell_line_Characteristics_22_11_s',
                      'Group_Name_Comment_22_11_s',
                      'REFINERY_TYPE_22_11_s',
                      'REFINERY_SUBANALYSIS_22_11_s']

        prettified_attributes = customize_attribute_response(attributes)
        self.assertListEqual(
                prettified_attributes,
                [{'data_type': 's',
                  'attribute_type': 'Factor Value',
                  'display_name': 'Treatment',
                  'internal_name': 'treatment_Factor_Value_22_11_s'},
                 {'data_type': 's',
                  'attribute_type': 'Characteristics',
                  'display_name': 'Treatment',
                  'internal_name': 'treatment_Characteristics_22_11_s'},
                 {'data_type': 's',
                  'attribute_type': 'Internal',
                  'display_name': 'Name',
                  'internal_name': 'REFINERY_NAME_22_11_s'},
                 {'data_type': 's',
                  'attribute_type': 'Characteristics',
                  'display_name': 'Strain',
                  'internal_name': 'strain_Characteristics_22_11_s'},
                 {'data_type': 's',
                  'attribute_type': 'Characteristics',
                  'display_name': 'Organism',
                  'internal_name': 'organism_Characteristics_22_11_s'},
                 {'data_type': 's',
                  'attribute_type': 'Internal',
                  'display_name': 'Output Type',
                  'internal_name': 'REFINERY_WORKFLOW_OUTPUT_22_11_s'},
                 {'data_type': 's',
                  'attribute_type': 'Comment',
                  'display_name': 'Replicate Id',
                  'internal_name': 'Replicate_Id_Comment_22_11_s'},
                 {'data_type': 's',
                  'attribute_type': 'Internal',
                  'display_name': 'Analysis',
                  'internal_name': 'REFINERY_ANALYSIS_UUID_22_11_s'},
                 {'data_type': 's',
                  'attribute_type': 'Internal',
                  'display_name': 'File Type',
                  'internal_name': 'REFINERY_FILETYPE_22_11_s'},
                 {'data_type': 's',
                  'attribute_type': 'Factor Value',
                  'display_name': 'Cell Line',
                  'internal_name': 'cell_line_Factor_Value_22_11_s'},
                 {'data_type': 's',
                  'attribute_type': 'Characteristics',
                  'display_name': 'Cell Line',
                  'internal_name': 'cell_line_Characteristics_22_11_s'},
                 {'data_type': 's',
                  'attribute_type': 'Comment',
                  'display_name': 'Group Name',
                  'internal_name': 'Group_Name_Comment_22_11_s'},
                 {'data_type': 's',
                  'attribute_type': 'Internal',
                  'display_name': 'Type',
                  'internal_name': 'REFINERY_TYPE_22_11_s'},
                 {'data_type': 's',
                  'attribute_type': 'Internal',
                  'display_name': 'Analysis Group',
                  'internal_name': 'REFINERY_SUBANALYSIS_22_11_s'}])

    def test_update_attribute_order_ranks(self):

        # Test basic increase
        attribute_order = AttributeOrder.objects.get(
                assay=self.assay,
                solr_field='Character_Title')
        new_rank = 5
        response = update_attribute_order_ranks(attribute_order, new_rank)
        attribute_list = AttributeOrder.objects.filter(
                assay=self.assay)

        self.assertEqual(response, 'Successful update')
        self.assertEqual(
                str(attribute_list),
                '[<AttributeOrder: Character_Title '
                '[facet = True exp = True act = True int = False] = 5>, '
                '<AttributeOrder: Specimen '
                '[facet = True exp = True act = True int = False] = 1>, '
                '<AttributeOrder: Cell Type '
                '[facet = True exp = True act = True int = False] = 2>, '
                '<AttributeOrder: Analysis '
                '[facet = True exp = True act = True int = False] = 3>, '
                '<AttributeOrder: Organism '
                '[facet = True exp = True act = True int = False] = 4>, '
                '<AttributeOrder: Cell Line '
                '[facet = True exp = True act = True int = False] = 6>, '
                '<AttributeOrder: Type '
                '[facet = True exp = True act = True int = False] = 7>, '
                '<AttributeOrder: Group Name '
                '[facet = True exp = True act = True int = False] = 8>, '
                '<AttributeOrder: Gene '
                '[facet = False exp = False act = True int = False] = 9>, '
                '<AttributeOrder: Replicate Id '
                '[facet = False exp = False act = True int = False] = 10>, '
                '<AttributeOrder: Organism Part '
                '[facet = False exp = False act = True int = False] = 0>, '
                '<AttributeOrder: Name '
                '[facet = False exp = False act = True int = False] = 0>]'
                )

        # Test top edge case
        attribute_order = AttributeOrder.objects.get(
                assay=self.assay,
                solr_field='Character_Title')
        new_rank = 10
        response = update_attribute_order_ranks(attribute_order, new_rank)
        attribute_list = AttributeOrder.objects.filter(
                assay=self.assay)

        self.assertEqual(response, 'Successful update')
        self.assertEqual(
                str(attribute_list),
                '[<AttributeOrder: Character_Title '
                '[facet = True exp = True act = True int = False] = 10>, '
                '<AttributeOrder: Specimen '
                '[facet = True exp = True act = True int = False] = 1>, '
                '<AttributeOrder: Cell Type '
                '[facet = True exp = True act = True int = False] = 2>, '
                '<AttributeOrder: Analysis '
                '[facet = True exp = True act = True int = False] = 3>, '
                '<AttributeOrder: Organism '
                '[facet = True exp = True act = True int = False] = 4>, '
                '<AttributeOrder: Cell Line '
                '[facet = True exp = True act = True int = False] = 5>, '
                '<AttributeOrder: Type '
                '[facet = True exp = True act = True int = False] = 6>, '
                '<AttributeOrder: Group Name '
                '[facet = True exp = True act = True int = False] = 7>, '
                '<AttributeOrder: Gene '
                '[facet = False exp = False act = True int = False] = 8>, '
                '<AttributeOrder: Replicate Id '
                '[facet = False exp = False act = True int = False] = 9>, '
                '<AttributeOrder: Organism Part '
                '[facet = False exp = False act = True int = False] = 0>, '
                '<AttributeOrder: Name '
                '[facet = False exp = False act = True int = False] = 0>]'
                )
        # Test bottom edge case
        attribute_order = AttributeOrder.objects.get(
                assay=self.assay,
                solr_field='Character_Title')
        new_rank = 1
        response = update_attribute_order_ranks(attribute_order, new_rank)
        attribute_list = AttributeOrder.objects.filter(
                assay=self.assay)

        self.assertEqual(response, 'Successful update')
        self.assertEqual(
                str(attribute_list),
                '[<AttributeOrder: Character_Title '
                '[facet = True exp = True act = True int = False] = 1>, '
                '<AttributeOrder: Specimen '
                '[facet = True exp = True act = True int = False] = 2>, '
                '<AttributeOrder: Cell Type '
                '[facet = True exp = True act = True int = False] = 3>, '
                '<AttributeOrder: Analysis '
                '[facet = True exp = True act = True int = False] = 4>, '
                '<AttributeOrder: Organism '
                '[facet = True exp = True act = True int = False] = 5>, '
                '<AttributeOrder: Cell Line '
                '[facet = True exp = True act = True int = False] = 6>, '
                '<AttributeOrder: Type '
                '[facet = True exp = True act = True int = False] = 7>, '
                '<AttributeOrder: Group Name '
                '[facet = True exp = True act = True int = False] = 8>, '
                '<AttributeOrder: Gene '
                '[facet = False exp = False act = True int = False] = 9>, '
                '<AttributeOrder: Replicate Id '
                '[facet = False exp = False act = True int = False] = 10>, '
                '<AttributeOrder: Organism Part '
                '[facet = False exp = False act = True int = False] = 0>, '
                '<AttributeOrder: Name '
                '[facet = False exp = False act = True int = False] = 0>]'
                )
        # Test removing a rank to 0
        attribute_order = AttributeOrder.objects.\
            get(assay=self.assay, solr_field='Character_Title')
        new_rank = 0
        response = update_attribute_order_ranks(attribute_order, new_rank)
        attribute_list = AttributeOrder.objects.filter(
                assay=self.assay)

        self.assertEqual(response, 'Successful update')
        self.assertEqual(
                str(attribute_list),
                '[<AttributeOrder: Character_Title '
                '[facet = True exp = True act = True int = False] = 0>, '
                '<AttributeOrder: Specimen '
                '[facet = True exp = True act = True int = False] = 1>, '
                '<AttributeOrder: Cell Type '
                '[facet = True exp = True act = True int = False] = 2>, '
                '<AttributeOrder: Analysis '
                '[facet = True exp = True act = True int = False] = 3>, '
                '<AttributeOrder: Organism '
                '[facet = True exp = True act = True int = False] = 4>, '
                '<AttributeOrder: Cell Line '
                '[facet = True exp = True act = True int = False] = 5>, '
                '<AttributeOrder: Type '
                '[facet = True exp = True act = True int = False] = 6>, '
                '<AttributeOrder: Group Name '
                '[facet = True exp = True act = True int = False] = 7>, '
                '<AttributeOrder: Gene '
                '[facet = False exp = False act = True int = False] = 8>, '
                '<AttributeOrder: Replicate Id '
                '[facet = False exp = False act = True int = False] = 9>, '
                '<AttributeOrder: Organism Part '
                '[facet = False exp = False act = True int = False] = 0>, '
                '<AttributeOrder: Name '
                '[facet = False exp = False act = True int = False] = 0>]'
                )

        # Test multiple changes, including inserting field back in rank order
        attribute_order = AttributeOrder.objects.\
            get(assay=self.assay, solr_field='Character_Title')
        new_rank = 7
        update_attribute_order_ranks(attribute_order, new_rank)
        AttributeOrder.objects.filter(assay=self.assay)
        attribute_order = AttributeOrder.objects.get(
                                                    assay=self.assay,
                                                    solr_field='Type')
        new_rank = 9
        update_attribute_order_ranks(attribute_order, new_rank)
        AttributeOrder.objects.filter(assay=self.assay)
        attribute_order = AttributeOrder.objects.get(
                                                    assay=self.assay,
                                                    solr_field='Name')
        new_rank = 3
        response = update_attribute_order_ranks(attribute_order, new_rank)
        attribute_list = AttributeOrder.objects.filter(
                assay=self.assay)

        self.assertEqual(response, 'Successful update')
        self.assertEqual(
                str(attribute_list),
                '[<AttributeOrder: Character_Title '
                '[facet = True exp = True act = True int = False] = 7>, '
                '<AttributeOrder: Specimen '
                '[facet = True exp = True act = True int = False] = 1>, '
                '<AttributeOrder: Cell Type '
                '[facet = True exp = True act = True int = False] = 2>, '
                '<AttributeOrder: Analysis '
                '[facet = True exp = True act = True int = False] = 4>, '
                '<AttributeOrder: Organism '
                '[facet = True exp = True act = True int = False] = 5>, '
                '<AttributeOrder: Cell Line '
                '[facet = True exp = True act = True int = False] = 6>, '
                '<AttributeOrder: Type '
                '[facet = True exp = True act = True int = False] = 10>, '
                '<AttributeOrder: Group Name '
                '[facet = True exp = True act = True int = False] = 8>, '
                '<AttributeOrder: Gene '
                '[facet = False exp = False act = True int = False] = 9>, '
                '<AttributeOrder: Replicate Id '
                '[facet = False exp = False act = True int = False] = 11>, '
                '<AttributeOrder: Organism Part '
                '[facet = False exp = False act = True int = False] = 0>, '
                '<AttributeOrder: Name '
                '[facet = False exp = False act = True int = False] = 3>]'
                )
        # Test small rank change
        attribute_order = AttributeOrder.objects.get(
                                                    assay=self.assay,
                                                    solr_field='Cell Line')
        new_rank = 5
        response = update_attribute_order_ranks(attribute_order, new_rank)
        attribute_list = AttributeOrder.objects.filter(
                assay=self.assay)

        self.assertEqual(response, 'Successful update')
        self.assertEqual(
                str(attribute_list),
                '[<AttributeOrder: Character_Title '
                '[facet = True exp = True act = True int = False] = 7>, '
                '<AttributeOrder: Specimen '
                '[facet = True exp = True act = True int = False] = 1>, '
                '<AttributeOrder: Cell Type '
                '[facet = True exp = True act = True int = False] = 2>, '
                '<AttributeOrder: Analysis '
                '[facet = True exp = True act = True int = False] = 4>, '
                '<AttributeOrder: Organism '
                '[facet = True exp = True act = True int = False] = 6>, '
                '<AttributeOrder: Cell Line '
                '[facet = True exp = True act = True int = False] = 5>, '
                '<AttributeOrder: Type '
                '[facet = True exp = True act = True int = False] = 10>, '
                '<AttributeOrder: Group Name '
                '[facet = True exp = True act = True int = False] = 8>, '
                '<AttributeOrder: Gene '
                '[facet = False exp = False act = True int = False] = 9>, '
                '<AttributeOrder: Replicate Id '
                '[facet = False exp = False act = True int = False] = 11>, '
                '<AttributeOrder: Organism Part '
                '[facet = False exp = False act = True int = False] = 0>, '
                '<AttributeOrder: Name '
                '[facet = False exp = False act = True int = False] = 3>]'
                )

        # Test invalid cases
        attribute_order = AttributeOrder.objects.get(
                                                    assay=self.assay,
                                                    solr_field='Cell Line')
        response = update_attribute_order_ranks(attribute_order, -4)
        self.assertEqual(response, 'Invalid: rank must be integer >= 0')
        response = update_attribute_order_ranks(attribute_order, None)
        self.assertEqual(response,
                         'Invalid: rank must be a string or a number.')
        response = update_attribute_order_ranks(attribute_order, 5)
        self.assertEqual(response,
                         'Error: New rank == old rank')

        attribute_order = AttributeOrder.objects.get(
                                                    assay=self.assay,
                                                    solr_field='Specimen')
        # Test string type
        new_rank = str(9)
        response = update_attribute_order_ranks(attribute_order, new_rank)
        attribute_list = AttributeOrder.objects.filter(
                assay=self.assay)

        self.assertEqual(response, 'Successful update')
        self.assertEqual(
                str(attribute_list),
                '[<AttributeOrder: Character_Title '
                '[facet = True exp = True act = True int = False] = 6>, '
                '<AttributeOrder: Specimen '
                '[facet = True exp = True act = True int = False] = 9>, '
                '<AttributeOrder: Cell Type '
                '[facet = True exp = True act = True int = False] = 1>, '
                '<AttributeOrder: Analysis '
                '[facet = True exp = True act = True int = False] = 3>, '
                '<AttributeOrder: Organism '
                '[facet = True exp = True act = True int = False] = 5>, '
                '<AttributeOrder: Cell Line '
                '[facet = True exp = True act = True int = False] = 4>, '
                '<AttributeOrder: Type '
                '[facet = True exp = True act = True int = False] = 10>, '
                '<AttributeOrder: Group Name '
                '[facet = True exp = True act = True int = False] = 7>, '
                '<AttributeOrder: Gene '
                '[facet = False exp = False act = True int = False] = 8>, '
                '<AttributeOrder: Replicate Id '
                '[facet = False exp = False act = True int = False] = 11>, '
                '<AttributeOrder: Organism Part '
                '[facet = False exp = False act = True int = False] = 0>, '
                '<AttributeOrder: Name '
                '[facet = False exp = False act = True int = False] = 2>]'
                )
