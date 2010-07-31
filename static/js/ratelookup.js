$(function() {
	var availableTags = ["c++", "java", "php", "coldfusion", "javascript", "asp", "ruby", "python", "c", "scala", "groovy", "haskell", "perl"];
	$("input#field_hotel").autocomplete({
		source: "/services/autocomplete/hotels.json",
		minLength: 2,
		delay: 100,
		select: function(event, ui) {
			$('input#field_hotel').val(ui.item.name);
			$('input#field_hotel_id').val(ui.item.id);

			return false;
		}
	})
	.data("autocomplete")._renderItem =function(ul, item) {
		return $("<li></li>" )
			.data("item.autocomplete", item)
			.append("<a><span class=\"bold\">" + item.name + "</span>" + 
					"<br />" + item.city + ", " + item.country + 
					" - Category " + item.category + "</a>")
			.appendTo(ul);
	};
	
	
	$("span.ratecode_example").click(
		function() {
			$("input#field_ratecode").val($(this).text());
		}
	);
});