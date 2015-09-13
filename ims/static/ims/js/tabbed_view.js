"use strict";
$(document).ready(function(){
	var angle = 0;
	var tabs = $("li.tabbed, li.tabbed-left");
	var tab;
	var index;
	var div;
	for (index = 0; index < tabs.length; index++) {
		div = $(tabs[index]).attr("meta");
		if($(tabs[index]).hasClass("tabbed-selected")) {
			$("#" + div).show();
		} else {
			$("#" + div).hide();
		}
	}
    $("li.tabbed, li.tabbed-left").click(function(){
        for (index = 0; index < tabs.length; index++) {
        	div = $(tabs[index]).attr("meta");
        	$(tabs[index]).removeClass("tabbed-selected");
        	if($(tabs[index]).attr("meta") == $(this).attr("meta")) {
        		$("#" + div).show();
        		$(tabs[index]).addClass("tabbed-selected");
        	} else {
        		$("#" + div).hide();
        	}
        }
    });
});