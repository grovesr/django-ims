"use strict";
$(document).ready(function(){
	var angle = 0;
	var imgDiv = $("#product-image");
	var rotateInput = $("#rotation");
	$("#rotate-button").html("Rotate: "+angle);
	$("#save-picture").attr("disabled", "disabled");
    $("#rotate-button").click(function(){
    	angle = (angle+90)%360;
    	imgDiv.removeClass();
        imgDiv.addClass("rotate"+angle);
        $(this).html("Rotate: "+angle);
        rotateInput.attr("value", angle);
        if (angle == 0) {
        	$("#save-picture").attr("disabled", "disabled");
        } else {
        	$("#save-picture").removeAttr("disabled");
        }
    });
});