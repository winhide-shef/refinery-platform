'use strict';

describe('DataSetImport.state:', function () {
  var $location;
  var $state;
  var $templateCache;
  var $rootScope;
  var $window = {
    location: {
      pathname: '/data_set_manager/import/'
    }
  };

  function mockTemplate (templateRoute, tmpl) {
    $templateCache.put(templateRoute, tmpl || templateRoute);
  }

  beforeEach(function () {
    module(function ($provide) {
      $provide.value('$window', $window);
    });
  });

  beforeEach(function () {
    module('refineryApp');
    module('refineryRouter');
    module('refineryDataSetImport');

    inject(function ($injector) {
      $location = $injector.get('$location');
      $state = $injector.get('$state');
      $templateCache = $injector.get('$templateCache');
      $rootScope = $injector.get('$rootScope');
    });
  });

  describe('state', function () {
    function goTo (url) {
      $location.url(url);
      $rootScope.$digest();
    }

    beforeEach(function () {
      mockTemplate('/static/partials/data-set-import/views/import.html');
      mockTemplate('/static/partials/data-set-import/views/file-upload.html');
    });

    it('should be "import" when path is empty', function () {
      goTo('');
      expect($state.current.name).toEqual('import');
    });

    it('should be "import" when path is "/"', function () {
      goTo('/');
      expect($state.current.name).toEqual('import');
    });

    it(
      'should be "fileUpload" when path is "/upload"',
      function () {
        goTo('/upload');
        expect($state.current.name).toEqual('fileUpload');
      }
    );

    it('should be "import" when path is not existing', function () {
      goTo('/someNonExistentUrl');
      expect($state.current.name).toEqual('import');
    });
  });
});
