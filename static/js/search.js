$(document).ready(
	function() {
		var nights_select = $("select#field_nights");
		var nights_text = $("#nights_text");
		nights_select.change(function(event) {
			nights_text.text((parseInt(nights_select.val()) > 1) ? "nights." : "night.");
		});
		
		
		
		
		var map_icons_base = "http://www.google.com/intl/en_us/mapfiles/ms/micons/";
		var user_marker_image_url = "http://maps.google.com/mapfiles/ms/micons/man.png";

		
		google.setOnLoadCallback(function() {
			var hotels_map = null;
			var hotel_markers = [];
			
			var create_hotel_marker = function(hotel, i) {
				var hotel_marker = new google.maps.Marker({
					position: new google.maps.LatLng(hotel['coord']['lat'], hotel['coord']['lng']),
					map: hotels_map,
					title: hotel.name,
					//icon: "http://maps.google.com/mapfiles/ms/micons/man.png",
					//icon: "/static/images/numeric_icons/off_icons/red" + (i + 1) + ".png",
					zIndex: 0
				});
				
				return hotel_marker;
			}
			
			var create_user_marker = function(user_coord) {
			    var user_marker_image =
			        new google.maps.MarkerImage(user_marker_image_url,
			                                    new google.maps.Size(32,32),
			                                    new google.maps.Point(0,0),
			                                    new google.maps.Point(0,32));

			    var user_marker_image_shadow =
			        new google.maps.MarkerImage("http://maps.google.com/mapfiles/ms/micons/man.shadow.png",
			                                    new google.maps.Size(59, 32),
			                                    new google.maps.Point(0,0),
			                                    new google.maps.Point(0, 32));

			    var user_marker_options = {
			        position:   user_coord,
			        map:        hotels_map,
			        icon:       user_marker_image,
			        shadow:     user_marker_image_shadow,
			        clickable:  false,
			        title:      "You are here.",
			        zIndex:     999,
			        //draggable:  true
			    };

			    var user_marker = new google.maps.Marker(user_marker_options);
			
				/*
			    google.maps.event.addListener(user_marker, 'mousedown',
			        function() {
			            $("#user_marker_tooltip").tipsy("hide");
			        }
			    );

			    google.maps.event.addListener(user_marker, 'dragend', 
			        function() {
			            var user_pos = user_marker.getPosition();

			            if (logged_in) {
			                update_user_location(user_pos, hotels_map.getZoom());
			            }

			            YUI.vendoori.helpers.lookup_city_state(user_pos,
			                YUI.vendoori.geocoder, 
			                function(user_loc) {
			                    populate_user_location(user_loc);
			                    update_hash();
			                });
			            populate_map(false);
			        }
			    );
				*/

			    return user_marker;
			}
			
			var update_map_bounds = function(user_coord) {
				if (nearest_hotels && nearest_hotels.length) {
					var bounds = new google.maps.LatLngBounds();
				    $.each(hotel_markers, function(i) {
			            bounds.extend(this.getPosition());
			        });  
				    bounds.extend(user_coord);
					hotels_map.fitBounds(bounds);
				}
			}
			
			
			/*
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
			*/
			
			var start_location;
			if (user_coord) {
				start_location = new google.maps.LatLng(user_coord['lat'], user_coord['lng']);
			}
			else {
				start_location = new google.maps.LatLng(37.42152, -122.08355);
			}
			
			hotels_map = new google.maps.Map(document.getElementById("hotels_map"), {
				zoom: 10,
				center: start_location,
				mapTypeId: google.maps.MapTypeId.ROADMAP,
				navigationControl: true,
				mapTypeControl: false,
				scaleControl: true,
				scrollwheel: false
			});
			
			var loaded = false;
		
			google.maps.event.addListener(hotels_map, 'tilesloaded', function() {
				//populate_map();
				if (!loaded) {
					$.each(nearest_hotels, function(i) {
						var hotel = this;
						var hotel_marker = create_hotel_marker(hotel);
						hotel_markers.push(hotel_marker);
					});
					
					if (user_coord) {
						var user_marker = create_user_marker(new google.maps.LatLng(user_coord['lat'], user_coord['lng']));
						update_map_bounds(user_marker.getPosition());
					}
					
					loaded = true;
				}
			});
		
			google.maps.event.addListener(hotels_map, 'dragend', function() {

			});
			
			if (google.loader.ClientLocation) {
				//console.log(google.loader.ClientLocation.latitude);
			}
		});
	}
);