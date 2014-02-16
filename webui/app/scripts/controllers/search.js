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

        $scope.sortOrder = '-posted';

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
					var results = response.data.rss.channel.item;

                    $scope.searchResults = [];
                    angular.forEach(results, function(obj) {
                        obj.pubDate = moment(obj.pubDate, "ddd, DD MMM YYYY HH:mm:ss ZZ").toDate();
                        $scope.searchResults.push(obj);
                    });

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
	})
    .filter('bytes', function() {
        return function(bytes, precision) {
            if (bytes==0 || isNaN(parseFloat(bytes)) || !isFinite(bytes)) { return '-'; }
            if (typeof precision === 'undefined') { precision = 1; }
            var units = ['bytes', 'kB', 'MB', 'GB', 'TB', 'PB'],
                number = Math.floor(Math.log(bytes) / Math.log(1024));
            return (bytes / Math.pow(1024, Math.floor(number))).toFixed(precision) +  ' ' + units[number];
        };
    });
