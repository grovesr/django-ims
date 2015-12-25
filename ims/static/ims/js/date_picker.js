"use strict";
$(document).ready(function() {
	var previousStartDate = date_to_mdy(new Date());
	var previousStopDate = date_to_mdy(new Date());
	function pad(num, size) {
	    var s = num + "";
	    while (s.length < size) {
	    	s = "0" + s;
	    }
	    return s;
	}
	function date_to_mdy(dateObject) {
		return pad(dateObject.getMonth()+1,2) + "-" + pad(dateObject.getDate(),2) + "-" + dateObject.getFullYear();
	}
	function validate_date(dateString, previousDateString) {
		var dateParts = dateString.toString().split('-');
		var timestamp = new Date(dateParts[2], dateParts[0]-1, dateParts[1], 0 ,0 ,0, 0).getTime();
		var newDate;
		if(isNaN(timestamp)) {
			newDate = previousDateString;
		}else {
			newDate =date_to_mdy(new Date(timestamp));
		}
		return newDate;
	}
    $("#startDate").change(function(){
    	$(this).val(validate_date($(this).val(), previousStartDate));
    	previousStartDate = $(this).val();
        var query = "?";
        $("[id$=Date]").each(function(){
            var thisDate =$(this).val();
            var thisParam = $(this).attr("id");
            query += thisParam + "=" + thisDate + "&";
        });
        $("[id$=-print]").each(function(){
            var basePath = $(this).attr("href").replace(/\?.*/,"");
            $(this).attr("href", basePath + query.slice(0,-1));
        });
    });
    $("#stopDate").change(function(){
    	$(this).val(validate_date($(this).val(), previousStopDate));
    	previousStopDate = $(this).val();
        var query = "?";
        $("[id$=Date]").each(function(){
            var thisDate = $(this).val();
            var thisParam = $(this).attr("id");
            query += thisParam + "=" + thisDate + "&";
        });
        $("[id$=-print]").each(function(){
            var basePath = $(this).attr("href").replace(/\?.*/,"");
            $(this).attr("href", basePath + query.slice(0,-1));
        });
    });
    var startDate = $('#startDate').val();
    var stopDate = $('#stopDate').val();
    $('#startDate').attr('class','datepicker');
    $('#stopDate').attr('class','datepicker');
    $('.datepicker').datepicker();
    $('.datepicker').datepicker("option", "dateFormat", "mm-dd-yy");
    $( '#startDate' ).val( startDate );
    $( '#stopDate' ).val( startDate );
    $( '#startDate' ).change();
    $( '#stopDate' ).change();
});