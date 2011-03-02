$(function() {
	var ratelookup_form = $("form#form_ratecode");
	
	var hotel_field = $("input#field_hotel", ratelookup_form);
	hotel_field.autocomplete({
		source: all_hotels,
		minLength: 1,
		select: function(event, ui) {
			hotel_field.val(ui.item.label);
			$("input#field_hotel_id", ratelookup_form).val(ui.item.value);

			return false;
		}
	}).data("autocomplete")._renderItem = function(ul, item) {
		var result_link = $("<a />"
			).append(
				$("<span />").attr("class", "bold").text(item.label)
			).append(
				$("<br />")
			).append(
				item.desc
			);
		return $("<li/>")
			.data("item.autocomplete", item)
			.append(result_link)
			.appendTo(ul);
	};
	
	
	$("input#field_date", ratelookup_form).datepicker({
		dateFormat: "yy-mm-dd",
		showOn: 'button',
		buttonImage: '/static2/images/calendar.gif',
		buttonImageOnly: true
	});
	
	
	$("span.ratecode_example", ratelookup_form).click(
		function() {
			$("input#field_ratecode", ratelookup_form).val($(this).text());
		}
	);
});