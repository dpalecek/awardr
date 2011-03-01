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
from app.models import StarwoodProperty, GeocodedLocation, StarwoodDateAvailability, StarwoodRatecode, StarwoodRateLookup
from app.parsers import StarwoodParser

try: import json
except ImportError: import simplejson as json

from lib.geomodel import geomodel
from lib.dateutil.relativedelta import relativedelta

import logging
logging.getLogger().setLevel(logging.DEBUG)


template.register_template_library('app.filters')


MILES_TO_METERS = 1609.344 # miles to meters
MAX_HOTELS_RESULTS = 30
MAX_HOTELS_DISTANCE = 70 * MILES_TO_METERS
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",)


def geocoder_service(address):
	url = "http://maps.google.com/maps/api/geocode/json?address=%s&sensor=%s" \
			% (urllib.quote_plus(helper.remove_accents(address)), "false")
	response = urlfetch.fetch(url)
	if response.status_code == 200:
		try:
			loc = json.loads(response.content)['results'][0]['geometry']['location']
			return db.GeoPt(loc['lat'], loc['lng'])
		except:
			pass

	return None


def get_start_date(req):
	today = datetime.date.today()
	
	try:
		month = int(req.get('month', today.month))
	except:
		month = today.month
	month = max(min(month, 12), 1)
		
	try:
		year = int(req.get('year', today.year))
	except:
		year = today.year
	year = max(min(year, today.year + 2), today.year)
	
	try:
		max_day = (calendar.mdays[month], 29)[calendar.isleap(year) and month == 2] #handle leap years
		day = min(int(req.get('day', today.day)), max_day)
	except:
		day = today.day
	
	return max(datetime.date(year, month, day), today)
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
		start_date = get_start_date(self.request)		
		
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
						# only show SPGCP if hotel category is less than 7
						if hotel.category < 7 and avail.ratecode == 'SPGCP':
							rate_key = 'SPGCP'
						else:
							rate_key = 'SPG'
							
						if rate_key:
							rates_data[rate_key] = avail.expand(nights)
							
					hotels_tuple[0].append((hotel, rates_data))
					
				else:
					hotels_tuple[1].append(hotel)
				
		
		template_values = helper.init_template_values(init_dict={ \
			'start_date': start_date,
			'days': xrange(1,32), 'months': MONTHS,
			'years': xrange(today.year, today.year + 3),
			'nights_range': xrange(1,6),
			'where': where, 'user_nights': nights,
			'user_location': geo_loc, 'foo': 0,
			'hotels_tuple': hotels_tuple,
			'nearest_hotels_json': [hotel.props() for hotel in nearest_hotels]
		}, uses_google_maps=True)
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
		if not all((arg in self.request.arguments()) for arg in ('hotel_id', 'ratecode', 'date')):
			template_values = { \
				'date': helper.date_to_str(datetime.date.today() + relativedelta(months=1))}
			
			self.response.out.write(template.render(helper.get_template_path("ratelookup"),
									template_values))
		else:
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
				date = helper.date_to_str(today)
				year, month, day = [int(p) for p in date.split('-')]
		
		
			template_values = {'ratecode': ratecode, 'hotel_id': hotel_id, 'hotel': hotel, \
								'date': date, 'submitted': True}
		
			if ratecode and hotel_id and date:
				date_ym = "%d-%02d" % (year, month)
				avail_data = StarwoodParser.parse_availability(hotel_id=hotel_id, ratecode=ratecode, \
																	start_date=date_ym, end_date=date_ym)
				if avail_data:
					currency_code = avail_data.get('currency_code')

					try:
						night = avail_data['availability'][year][month][day][1]
					except:
						night = None
			
					template_values['found'] = (night and (night.get('rate') or night.get('points') or night.get('pts'))) is not None
					if template_values['found']:
						template_values['currency_code'] = avail_data['currency_code']
						template_values['cash'] = night.get('rate')
						template_values['points'] = night.get('points') or night.get('pts')
				
						logging.info("\n\n\n%s\n\n\n" % template_values)
				
						ratecode_key_name = StarwoodRatecode.calc_key_name(ratecode)
						ratecode_entity = StarwoodRatecode.get_by_key_name(ratecode_key_name)
						if not ratecode_entity:
							ratecode_entity = StarwoodRatecode(key_name=ratecode_key_name, ratecode=ratecode)
							ratecode_entity.put()
					
						rate_lookup_key_name = StarwoodRateLookup.calc_key_name(hotel, ratecode_entity.ratecode, helper.str_to_date(date))
						rate_lookup_entity = StarwoodRateLookup.get_by_key_name(rate_lookup_key_name)
						if not rate_lookup_entity:
							rate_lookup_entity = StarwoodRateLookup(key_name=rate_lookup_key_name, hotel=hotel, \
																	ratecode=ratecode_entity, date=helper.str_to_date(date))
				
						if template_values['cash'] or template_values['points']:
							logging.info("%s" % template_values)
							if template_values['cash']:
								rate_lookup_entity.cash = float(template_values['cash'])
							if template_values['points']:
								rate_lookup_entity.points = int(template_values['points'])
							rate_lookup_entity.put()
					
						if template_values['cash'] and currency_code and currency_code.upper() != 'USD':
							converted = helper.currency_conversion(currency_code, template_values['cash'])
							if converted:
								template_values['to_usd'] = "%.2f" % converted
			
			self.response.out.write(template.render(helper.get_template_path("ratelookup"),
									template_values))



class BrowseCountryView(webapp.RequestHandler):
	def get(self, country_slug):
		country_slug = country_slug.lower()
		special_countries = { \
			'georgia': 'Georgia, Republic of',
			'maldives': 'Maldives, Republic of',
			'panama': 'Panama, Republic of',
		}
		country_name = special_countries.get(country_slug)
		if not country_name:
			country_name = ' '.join((country_part.capitalize() for country_part in country_slug.split('-')))
			
		template_values = {'country_name': country_name}
		hotels = StarwoodProperty.all().filter('country =', country_name).order('name')
		if hotels.count():
			template_values['hotels'] = hotels
			
		self.response.out.write(template.render(helper.get_template_path("browse_country"),
								template_values))
		
class BrowseCountriesIndexView(webapp.RequestHandler):
	def get(self):
		sort_by = self.request.get('sort', default_value='name')
		
		countries_count = defaultdict(int)
		for hotel in StarwoodProperty.all():
			countries_count[hotel.country] += 1
		countries = [{'name': country, 'count': count, 'slug': str('-'.join(country.split(',')[0].lower().split()))} \
						for country, count in countries_count.iteritems()]
		template_values = {'countries': sorted(countries, key=lambda country: country[sort_by], reverse=(sort_by == 'count')), \
							'sort_by': sort_by}
			
		self.response.out.write(template.render(helper.get_template_path("browse_countries"),
								template_values))


class BrowseView(webapp.RequestHandler):
	def get(self):
		self.redirect('/browse/countries')		


class HotelDetailView(webapp.RequestHandler):
	def get(self, hotel_id, slug):
		hotel = StarwoodProperty.get_by_id(hotel_id)
		logging.info("hotel: %s" % hotel)
		if not hotel:
			self.error(500)
		else:
			try:
				nights = int(self.request.get('nights', 1))
			except:
				nights = 1
			nights = max(min(nights, 5), 1)

			today = datetime.date.today()
			start_date = get_start_date(self.request)
			
			template_values = helper.init_template_values( \
				init_dict={'hotel': hotel, 'start_date': start_date, 'nights': nights},
				uses_google_maps=True)
			self.response.out.write(template.render(helper.get_template_path("hotel_detail"),
									template_values))
				
		


def main():
	ROUTES = [
		('/hotel/starwood/(\d*)/(.*)', HotelDetailView),
		('/browse/countries/(.*)', BrowseCountryView),
		('/browse/countries', BrowseCountriesIndexView),
		('/browse', BrowseView),
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