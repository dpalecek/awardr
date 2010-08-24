$(document).ready(function() {
	var start_location = new google.maps.LatLng(YUI.awardpad.hotel_coord['lat'], YUI.awardpad.hotel_coord['lng']);
	
	google.setOnLoadCallback(function() {
		var hotels_map = new google.maps.Map(document.getElementById("hotel_map"), {
			zoom: 10,
			center: start_location,
			mapTypeId: google.maps.MapTypeId.ROADMAP,
			navigationControl: true,
			mapTypeControl: false,
			scaleControl: true,
			scrollwheel: false
		});
	});
});