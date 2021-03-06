'use strict';

angular
  .module('refineryApp', [
    /*
     * Angular modules
     */
    'ngResource',

    /*
     * Third party modules
     */
    'ui.router',
    'ngWebworker',
    'file-model',

    /*
     * Angular App globals
     */
    'errors',
    'pubSub',
    'getCookie',
    'closeOnOuterClick',
    'colors',
    'focusOn',
    'clearFileInput',
    'replaceWhiteSpaceWithHyphen',

    /*
     * Refinery modules
     */
    'refineryRouter',
    'refineryWorkflows',
    'refineryNodeMapping',
    'refineryAnalysisLaunch',
    'refineryNodeRelationship',
    'refineryDataSetExplorer',
    'refineryStatistics',
    'refineryProvvis',
    'refineryDataSetImport',
    'refineryDataSetNav',
    'refineryDashboard',
    'refineryAnalysisMonitor',
    'refineryCollaboration',
    'refineryChart',
    'refineryFileBrowser',
    'refineryDataSetAbout'
  ])
  .run(['$', '$rootScope', function ($, $rootScope) {
    //  trigger from the contents.js when the node selection list has been
    // updated. Used by node_mapping.js Trigger for analyze tab view to run
    // analyses status.
    $(document).on('refinery/updateCurrentNodeSelection', function (e) {
      $rootScope.$broadcast(e.type);
      $rootScope.$digest();
    });
  }]);
