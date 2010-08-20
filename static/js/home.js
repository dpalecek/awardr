$(document).ready(
	function() {
		google.setOnLoadCallback(function() {
			var hotels_map = null;
			var hotel_markers = [];
			
			var hotel_results_list = $("ul#hotel_results_list");
		
			var populate_map = function() {
				hotel_results_list.empty();
				
				$.each(hotel_markers, function(i) {
					var hotel_marker = this;
					hotel_marker.setMap(null);
				});
			
				var bounds = hotels_map.getBounds();
			
				$.get('/services/hotels.json',
					{'w': bounds.getSouthWest().lat(), 's': bounds.getSouthWest().lng(),
						'e': bounds.getNorthEast().lat(), 'n': bounds.getNorthEast().lng()},
					function(response) {
						$.each(response['hotels'], function(i) {
							var hotel = this;
							
							hotel_results_list.append($("<li/>")
									.append($("<p/>").addClass("bold").text(hotel['name'] + " "))
									.append($("<span/>").text(hotel['city'] + ", " + hotel['country'] + " "))
									.append($("<span/>").text(" (" + hotel['category'] + ")"))
							);
							
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
			
			if (google.loader.ClientLocation) {
			}
		});
	}
);