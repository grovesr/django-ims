$(document).ready(function(){
		// create peudo uuid4 code (32 hex chars)
        $("#generate-code").click(function(){
        	var uuid = 'xxxxxxxxxxxx4xxxyxxxxxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        	    var r = Math.random()*16|0, v = c == 'x' ? r : (r&0x3|0x8);
        	    return v.toString(16);
        	});
            $("#id_code").attr('value',uuid);
        });
    });