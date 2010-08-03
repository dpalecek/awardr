$(function() {
	var hotels_source = "/services/autocomplete/hotels.json";
	
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
	
	
	$("span.ratecode_example").click(
		function() {
			$("input#field_ratecode").val($(this).text());
		}
	);
});