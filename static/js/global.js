YUI.namespace('awardpad');

var trace_alert = false;
YUI.awardpad.trace = function(s) {
	try { console.log(s); } catch (e) { if (trace_alert) { alert(s); } }
};