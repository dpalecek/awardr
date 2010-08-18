import os
import urllib
import random
import datetime
import calendar
import wsgiref.handlers
from collections import defaultdict

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch

from app import helper
from app.models import StarwoodProperty, GeocodedLocation, StarwoodDateAvailability
from app.parsers import StarwoodParser

try: import json
except ImportError: import simplejson as json

from lib.geomodel import geomodel
from lib.dateutil.relativedelta import relativedelta

import logging
logging.getLogger().setLevel(logging.DEBUG)


template.register_template_library('app.filters')


MILES_TO_METERS = 1609.344 # miles to meters
MAX_HOTELS_RESULTS = 20
MAX_HOTELS_DISTANCE = 100 * MILES_TO_METERS
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",)


def geocoder_service(address):
	url = "http://maps.google.com/maps/api/geocode/json?address=%s&sensor=%s" \
			% (urllib.quote_plus(address), "false")
	response = urlfetch.fetch(url)
	if response.status_code == 200:
		try:
			loc = json.loads(response.content)['results'][0]['geometry']['location']
			return db.GeoPt(loc['lat'], loc['lng'])
		except:
			pass

	return None


'''
cash & points
https://www.starwoodhotels.com/preferredguest/booking/cash_points/rates.html?numberOfAdults=2&propertyID=1234&arrivalDate=2010-09-05&departureDate=2010-09-06

points
https://www.starwoodhotels.com/preferredguest/booking/points/rates.html?numberOfRooms=1&numberOfAdults=2&arrivalDate=2010-09-05&departureDate=2010-09-06&lengthOfStay=1&propertyID=1234&rateCategory=SPG6&roomOccupancyTotal=2
'''
class SearchView(webapp.RequestHandler):
	def get(self):
		try:
			nights = int(self.request.get('nights', 1))
		except:
			nights = 1
		nights = max(min(nights, 5), 1)
		
		today = datetime.date.today()
		
		try:
			month = int(self.request.get('month', today.month))
		except:
			month = today.month
		month = max(min(month, 12), 1)
			
		try:
			year = int(self.request.get('year', today.year))
		except:
			year = today.year
		year = max(min(year, today.year + 2), today.year)
		
		try:
			max_day = (calendar.mdays[month], 29)[calendar.isleap(year) and month == 2] #handle leap years
			day = min(int(self.request.get('day', today.day)), max_day)
		except:
			day = today.day
		
		start_date = max(datetime.date(year, month, day), today)
		
		
		where = self.request.get('where', default_value='').strip()
		if where:
			geo_loc = GeocodedLocation.getter(where)
			if not geo_loc:
				geo_loc = geocoder_service(where)
				GeocodedLocation.setter(where, geo_loc)
		else:
			geo_loc = None
			
		if geo_loc:
			nearest_hotels = StarwoodProperty.proximity_fetch( \
						StarwoodProperty.all().filter('location != ', 'NULL'),
						geo_loc, max_results=MAX_HOTELS_RESULTS,
						max_distance=MAX_HOTELS_DISTANCE)
		else:
			nearest_hotels = []
			
			
		hotels_tuple = ([], [],)

		if nearest_hotels:
			avail_dict = defaultdict(list)
			for k, v in [(avail.hotel.id, avail) for avail in \
							StarwoodDateAvailability.all().filter('date =', start_date).filter('nights =', nights).filter('hotel IN', nearest_hotels).order('date')]:
				avail_dict[k].append(v)
			
			for hotel in nearest_hotels:
				if hotel.id in avail_dict.keys():
					rates_data = {}
					for avail in avail_dict[hotel.id]:
						if avail.ratecode == 'SPGCP':
							rate_key = 'SPGCP'
						else:
							rate_key = 'SPG'
						rates_data[rate_key] = avail.expand(nights)
					hotels_tuple[0].append((hotel, rates_data))
				else:
					hotels_tuple[1].append(hotel)
				
		
		template_values = { \
			'start_date': start_date,
			'days': xrange(1,32), 'months': MONTHS,
			'years': xrange(today.year, today.year + 3),
			'nights_range': xrange(1,6),
			'where': where, 'user_nights': nights,
			'user_location': geo_loc, 'foo': 0,
			'hotels_tuple': hotels_tuple,
			'nearest_hotels_json': [hotel.props() for hotel in nearest_hotels]
		}
		self.response.out.write(template.render(helper.get_template_path("search"),
								template_values))
		
		
		
class LandingView(webapp.RequestHandler):
	def get(self):
		today = datetime.date.today()
		start_day = today + relativedelta(months=1)

		all_hotels = StarwoodProperty.all()
		if all_hotels and all_hotels.count():
			hotel = random.choice(all_hotels.fetch(2000))
		else:
			hotel = None
		
		template_values = {'days': xrange(1,32), 'months': MONTHS, \
							'years': xrange(today.year, today.year + 3),
							'start_day': start_day,	'hotel': hotel}
		self.response.out.write(template.render(helper.get_template_path("landing"),
								template_values))
		
		
class StarwoodPropertyView(webapp.RequestHandler):
	def get(self, id):
		self.response.headers['Content-Type'] = 'text/plain'
		try:
			property_id = int(id)
		except:
			property_id = None
		hotel = StarwoodProperty.all().filter('id =', property_id).get()
		if hotel:
			self.response.out.write("%s" % hotel.props())
		else:
			self.response.out.write("Property with id '%s' not found." % (id))
		
		if self.request.get('geocode', None) == 'true':
			self.response.out.write("\n\ngeocoded: %s" % (hotel.geocode()))
		
		
		
class StarwoodPropertiesView(webapp.RequestHandler):
	def get(self):
		template_values = {}
		
		hotels = StarwoodProperty.all().order('id')
		category = int(self.request.get("category", 0))
		if category:
			hotels = hotels.filter('category =', category)
		
		template_values['hotels'] = hotels
		self.response.out.write(template.render(helper.get_template_path("starwood"),
								template_values))



class RateLookupView(webapp.RequestHandler):
	def get(self):		
		night = datetime.date.today() #+ datetime.timedelta(days=30)
		template_values = {'date': "%d-%02d-%02d" % (night.year, night.month, night.day)}
			
		self.response.out.write(template.render(helper.get_template_path("ratelookup"),
								template_values))
								
	def post(self):
		# ratecode param
		ratecode = self.request.get('ratecode', default_value='').strip().upper()
		if not (ratecode and len(ratecode)):
			ratecode = 'RACK'
		
		# hotel param
		try:
			hotel_id = int(self.request.get('hotel_id', default_value="-1").strip())
		except:
			hotel_id = None
			
		if hotel_id:
			hotel = StarwoodProperty.get_by_id(id=hotel_id)
			
		if not hotel_id:
			hotel_name = self.request.get('hotel', default_value='').strip()
			
			# try to look up the hotel based on name
			if hotel_name and len(hotel_name):
				hotel = StarwoodProperty.get_by_prop(prop='name', value='hotel_name')
			else:
				hotel = None
				
			# just pick a random hotel if no hotel id or name specified
			if not hotel:
				hotel = StarwoodProperty.random()
				
			hotel_id = hotel.id
		
		# data param
		date = self.request.get('date', default_value='').strip()
		try:
			year, month, day = [int(p) for p in date.split('-')]
		except:
			today = datetime.date.today()
			date = "%d-%02d-%02d" % (today.year, today.month, today.day)
			year, month, day = [int(p) for p in date.split('-')]
		
		
		template_values = {'ratecode': ratecode, 'hotel_id': hotel_id, 'hotel': hotel, \
							'date': date, 'submitted': True}
		
		if ratecode and hotel_id and date:
			date_ym = "%d-%02d" % (year, month)
			avail_data = StarwoodParser.parse_availability(hotel_id=hotel_id, ratecode=ratecode, \
																start_date=date_ym, end_date=date_ym)
			
			logging.info("\n\n\n%s\n\n\n" % avail_data)

			try:
				night = avail_data['availability'][year][month][day][1]
			except:
				night = None
			
			template_values['found'] = night is not None
			if night:
				template_values['currency_code'] = avail_data['currency_code']
				template_values['rate'] = night.get('rate')
				template_values['points'] = night.get('points') or night.get('pts')

		self.response.out.write(template.render(helper.get_template_path("ratelookup"),
								template_values))


def main():
	ROUTES = [
		('/rate-lookup', RateLookupView),
		('/search', SearchView),
		('/starwood/(.*)', StarwoodPropertyView),
		('/starwood', StarwoodPropertiesView),
		('/', LandingView),
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)


if __name__ == "__main__":
	main()