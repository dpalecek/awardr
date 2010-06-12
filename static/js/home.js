$(document).ready(
	function() {
		var hotels_map = null;
		var hotel_markers = [];
		
		var populate_map = function() {
			$.each(hotel_markers, function(i) {
				var hotel_marker = this;
				hotel_marker.setMap(null);
			});
			
			var bounds = hotels_map.getBounds();
			console.log(bounds);
			
			$.get('/services/hotels.json',
				{'w': bounds.getSouthWest().lat(), 's': bounds.getSouthWest().lng(),
					'e': bounds.getNorthEast().lat(), 'n': bounds.getNorthEast().lng()},
				function(response) {
					$.each(response['hotels'], function(i) {
						var hotel = this;
						var hotel_marker = new google.maps.Marker({
							position: new google.maps.LatLng(hotel['coord']['lat'], hotel['coord']['lng']), 
							map: hotels_map, 
							title: hotel['name']
						});
						google.maps.event.addListener(hotel_marker, 'mouseover', function() {
							$("p#info").empty().text(hotel['name']);
						});
						
						hotel_markers.push(hotel_marker);
					});
				}
			);
		}
		
		hotels_map = new google.maps.Map(document.getElementById("map_canvas"), {
			zoom: 6,
			center: new google.maps.LatLng(-34.397, 150.644),
			mapTypeId: google.maps.MapTypeId.ROADMAP,
			navigationControl: true,
			mapTypeControl: false,
			scaleControl: true,
			scrollwheel: false
		});
		
		/*
		google.maps.event.addListener(hotels_map, 'tilesloaded', function() {
			populate_map();
		});
		*/
		
		google.maps.event.addListener(hotels_map, 'dragend', function() {
			populate_map();
		});
	}
);