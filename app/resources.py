# All the resources go here.

CATEGORY_AWARD_CHOICES = {
	'cash_points': {
		1: {'points': 1200, 'cash': 25,},
		2: {'points': 1600, 'cash': 30,},
		3: {'points': 4000, 'cash': 45,},
		4: {'points': 4000, 'cash': 60,},
		5: {'points': 4800, 'cash': 90,},
		6: {'points': 8000, 'cash': 150,},
	},

	# {category: [weekday, weekend]}
	'points': {
		1: [{'min': 3000, 'max': 3000}, {'min': 2000, 'max': 2000}],
		2: [{'min': 4000, 'max': 4000}, {'min': 3000, 'max': 3000}],
		3: [{'min': 7000, 'max': 7000}, {'min': 7000, 'max': 7000}],
		4: [{'min': 10000, 'max': 10000}, {'min': 10000, 'max': 10000}],
		5: [{'min': 12000, 'max': 16000}, {'min': 12000, 'max': 16000}],
		6: [{'min': 20000, 'max': 25000}, {'min': 20000, 'max': 25000}],
		7: [{'min': 30000, 'max': 35000}, {'min': 30000, 'max': 35000}],
	},
}