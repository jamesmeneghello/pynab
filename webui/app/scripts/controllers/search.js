'use strict';

angular.module('pynabWebuiApp')
	.controller('SearchCtrl', function ($scope, $http, $cookieStore, PYNAB_CONFIG) {
		$scope.searchForm = {};

		if ($cookieStore.get('apikey')) {
			$scope.searchForm.apikey = $cookieStore.get('apikey');
		}

		if ($cookieStore.get('remember')) {
			$scope.searchForm.remember = $cookieStore.get('remember');
		}

		var params = {
			t: 'caps',
			o: 'json',
			callback:'JSON_CALLBACK'
		};

		$http.jsonp(PYNAB_CONFIG.hostUrl + 'api', {params:params}).then(function(response) {
			var categories = [];
			response.data.caps.categories.category.forEach(function(category) {
				if (category.subcat instanceof Array) {
					category.subcat.forEach(function(subcategory) {
						subcategory.name = category.name + ' > ' + subcategory.name;
						categories.push(subcategory);
					});
				} else {
					category.subcat.name = category.name + ' > ' + category.subcat.name;
					categories.push(category.subcat);
				}
			});
			$scope.categories = categories;
		});

		$scope.search = function() {
			$scope.searchResults = null;
			$scope.errorApikey = null;

			var params = {
				t: 'search',
				o: 'json',
				limit: 100,
				cat: $scope.searchForm.cat.join(),
				q: $scope.searchForm.q,
				apikey: $scope.searchForm.apikey,
				callback:'JSON_CALLBACK'
			};
			
			$http.jsonp(PYNAB_CONFIG.hostUrl + 'api', {params:params}).then(function(response) {
				if ('error' in response.data) {
					var error = response.data.error;
					if (error.code === '100') {
						$scope.errorApikey = error.description;
					}
				} else {
					$scope.searchResults = response.data.rss.channel.item;
					console.log(response.data);

					if ($scope.searchForm.remember) {
						$cookieStore.put('remember', true);
						$cookieStore.put('apikey', $scope.searchForm.apikey);
					} else {
						$cookieStore.put('remember', false);
						$cookieStore.put('apikey', '');
					}
				}
			});
		};
	});
