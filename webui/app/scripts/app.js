'use strict';

angular.module('pynabWebuiApp', ['ui.router','angularMoment', 'ngCookies'])
  .config(function ($stateProvider, $urlRouterProvider) {
	$urlRouterProvider.otherwise('/');

    $stateProvider
      .state('index', {
        url: '/',
        views: {
          'content': {templateUrl: 'views/index.html'}
        }
      })
      .state('search', {
        url: '/search',
        views: {
          'content': {templateUrl: 'views/search.html', controller: 'SearchCtrl'}
        }
      })
      .state('about', {
        url: '/about',
        templateUrl: 'views/about.html'
      });
  })
  .run(['$rootScope', '$state', '$stateParams', function($rootScope, $state, $stateParams) {
    $rootScope.$state = $state;
    $rootScope.$stateParams = $stateParams;
  }]);
