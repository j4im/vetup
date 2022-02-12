
/*
$('.datepicker').datepicker({
    startView: 2,
    minViewMode: 2,
    maxViewMode: 2,
    multidate: true,
	format: " yyyy"
});

var urlParams;
(window.onpopstate = function () {
    var match,
        pl     = /\+/g,  // Regex for replacing addition symbol with a space
        search = /([^&=]+)=?([^&]*)/g,
        decode = function (s) { return decodeURIComponent(s.replace(pl, " ")); },
        query  = window.location.search.substring(1);

    urlParams = {};
    while (match = search.exec(query))
       urlParams[decode(match[1])] = decode(match[2]);
})();

if (urlParams['years'] !== undefined) {
	years = urlParams['years'].split(",")
	dates = []
	for(i=0; i < years.length; i++) {
		year = parseInt(years[i].trim(), 10)
		if (!isNaN(year) && year > 1900 && year < 2100) {
			date = new Date(years[i].trim(), 0)
			if (!isNaN(date.getTime())) {
				dates.push(date)
			}
		}
	}
	$('.datepicker').datepicker('setUTCDate',dates);
}
*/

