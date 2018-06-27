function getUrlParams(url) {
	var urlParams = {};
	var paramPairs = url.slice(url.indexOf('?') + 1).split('&');
	paramPairs.forEach(function(eachPair) {
		if (eachPair != "") {
			pair = eachPair.split("=");
			if(pair.length > 1) {
				urlParams[pair[0]] = decodeURIComponent(pair[1].replace(/\+/g, " "));
			} else {
				urlParams[pair[0]] = null;
			}
		}
	})
	return urlParams;
}
$(document).ready(function(){
	var search = false;
	filterParams = getUrlParams(window.location.href);
	if(!filterParams['searchValue']) {
		$(".filter-row").hide();
	} else {
		$(".filter-btn").each( function() {
			var filterHeader = $(this).parent();
			var filterField = filterHeader.attr("id").slice(7);
			if(filterField == filterParams["searchField"]) {
				$(this).siblings(".filter-field").val(filterParams["searchValue"]);
			}
		});
		search = true;
		$("i.search").removeClass("search-off").addClass("search-on");
	}
	$("form").on("keypress", "input", function(event) {
		// prevent enter from submitting form so we can have 
		// enter submit search when focus is search field
		if(event.keyCode === 13) {
			return false;
		}
	});
	
	$("i.search").click(function(){
		if(search) {
			search = false;
			$(this).removeClass("search-on").addClass("search-off");
			$(".filter-row").fadeOut();
		} else {
			search = true;
			$(this).removeClass("search-off").addClass("search-on");
			$(".filter-row").fadeIn();
			$(".filter-field").filter(":visible").first().focus();
		}
		
	})
	
	$(".filter-field").each( function() {
		// enable enter key to initiate search when search field has focus 
		$(this).keyup(function(event) {
			if (event.keyCode === 13) {
				$(this).siblings('.filter-btn').first().click();
			}
		});
	});
	
	$("select.filter-field ").each( function() {
		// enable select change to initiate search when search field has focus 
		$(this).change(function(event) {
			$(this).siblings('.filter-btn').first().click();
		});
	});
	
	$(".filter-btn").each( function() {
		$(this).click(function(){
			var filterHeader = $(this).parent();
			var filterField = filterHeader.attr("id").slice(7);
			var filterValue = filterHeader.find("input, select").val().trim();
			var url = $(location).attr("href");
			var argBegin = url.indexOf('?')
			var path;
			if(argBegin > 0) {
				path = url.slice(0,argBegin);
			} else {
				path = url;
			}
			if(filterValue === 'all') {
				$(location).attr("href", path + "?page=1");
				return;
			}
			$(location).attr("href", path + "?page=1&searchField=" + filterField + "&searchValue=" + filterValue);
		})
	});
})