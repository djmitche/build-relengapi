/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

angular.module('root', []);

angular.module('root').directive('rootWidgetGrid', function($timeout) {
    return {
        link: function (scope, element, attrs) {
            var options = attrs['masonryOptions'] || '{}';
            options = JSON.parse(options);
            options.isInitLayout = false;
            scope.msnry = new Masonry(element.get(0), options);
            // delay layout until the child elements are loaded
            $timeout(function() { scope.msnry.layout(); });
        },
        scope: {},
        restrict: 'E',
        replace: true,
        transclude: true,
        template: '<div ng-transclude></div>',
    };
});

angular.module('root').directive('rootWidget', function() {
    return {
        link: function (scope, element, attrs) {
            scope.title = attrs['title'] || 'Anonymous Widget';
            scope.href = attrs['href'] || '#';
            // allow up to two columns (the maximum for small screens)
            scope.columns = Math.min(parseInt(attrs['columns'] || "1"), 2);
        },
        restrict: 'E',
        transclude: true,
        replace: true,
        scope: {},
        template: '<div class="root-widget w{{columns}}">' + 
                  '<h1><a href="{{href}}">{{title}}</a></h1>' + 
                  '<div ng-transclude></div></div>',
    };
});
