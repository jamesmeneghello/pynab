'use strict';

var pynabWebuiApp = angular.module('pynabWebuiApp', ['ngRoute', 'angularMoment', 'ngCookies', 'ui.bootstrap', 'ngResource']);

pynabWebuiApp.config(['$routeProvider', function($routeProvider) {
    $routeProvider.
    when('/', {templateUrl: 'views/index.html', controller: 'IndexCtrl'}).
    when('/search', {templateUrl: 'views/search.html', controller: 'SearchCtrl'}).
    when('/about', {templateUrl: 'views/about.html'}).
    otherwise({redirectTo: '/'});
  }]);