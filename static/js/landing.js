$(function() {
	var field_where = $("input#field_where");
	$("span.example_location").click(
		function() {
			field_where.val($(this).text());
		}
	);
});