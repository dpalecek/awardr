$(document).ready(function() {
	console.log(all_hotels.length);
	$("input#field_hotel").autocomplete(all_hotels, {
			minChars: 0,
			width: 200,
			autoFill: false,
			mustMatch: false,
			dataType: 'json',
			scroll: true,
			scrollHeight: 300,
			parse: function(data) {
				var results = [];
				$.each(data['results'], function(i) {
					results.push({'data': this, 'value': this['name'], 'result': this['name']});
				});
				return results;
			},
			formatItem: function(item) {
				return "<span class=\"result_name\"><span class=\"bold\">" + item.name + "</span></span>" + 
						"<br /><span class=\"result_extra\">" + item.city + ", " + item.country + 
						" - Category " + item.category + "</span>";
				/*
				var location = null;
				if(item['city'] && item['city'].length > 1) {
					location = item['city'] + ", " + item['state']
				}
				else {
					location = item['state'];
				}
	
				return "<span class=\"result_name\">" + item['name'] + "</span>"
						+ "<span class=\"result_extra\">" + location + "</span>";
				*/
			}
		}
	);

	/*
	//var hotels_source = "/services/autocomplete/hotels.json";
	var hotels_source = all_hotels;
	
	$("input#field_hotel").autocomplete({
		source: hotels_source,
		minLength: 3,
		//delay: 2000,
		select: function(event, ui) {
			$('input#field_hotel').val(ui.item.name);
			$('input#field_hotel_id').val(ui.item.id);

			return false;
		}
	})
	.data("autocomplete")._renderItem = function(ul, item) {
		return $("<li/>")
			.data("item.autocomplete", item)
			.append(
				$("<a/>").append("<span class=\"bold\">" + item.name + "</span>" + 
					"<br />" + item.city + ", " + item.country + 
					" - Category " + item.category))
			.appendTo(ul);
	};
	*/
	
	
	$("span.ratecode_example").click(
		function() {
			$("input#field_ratecode").val($(this).text());
		}
	);
});