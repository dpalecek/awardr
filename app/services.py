import os
import wsgiref.handlers

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch
from google.appengine.api import memcache

from app import helper
from app.parsers import StarwoodParser
from app.models import StarwoodProperty

import simplejson

import logging
logging.getLogger().setLevel(logging.DEBUG)

def in_viewport(coord, sw, ne):
	return coord.lat >= min(sw['lat'], ne['lat']) and coord.lat <= max(sw['lat'], ne['lat']) \
			and coord.lon >= min(sw['lng'], ne['lng']) and coord.lon <= max(sw['lng'], ne['lng'])


class AllHotels(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'application/json'
		self.response.out.write(simplejson.dumps( \
			{'hotels': [hotel.props() for hotel in StarwoodProperty.all()]}))


class HotelsLookup(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'application/json'
		
		try:
			sw = {'lat': float(self.request.get('w')), 'lng': float(self.request.get('s'))}
		except:
			sw = None
		try:
			ne = {'lat': float(self.request.get('e')), 'lng': float(self.request.get('n'))}
		except:
			ne = None
		
		hotels = memcache.get('hotels')
		if not hotels:
			hotels = [hotel for hotel in StarwoodProperty.all().filter('coord !=', None)]
			memcache.set('hotels', hotels)
		
		if sw and ne:
			hotels = [hotel for hotel in hotels if in_viewport(hotel.coord, sw, ne)]
		
		self.response.out.write(simplejson.dumps({'hotels': [hotel.props() for hotel in hotels]}))


class HotelAvailability(webapp.RequestHandler):
	def get(self, hotel_id):
		self.response.headers['Content-Type'] = 'application/json'
		
		try:
			hotel_id = int(hotel_id)
		except:
			hotel_id = 0
		
		start_date = self.request.get('start_date')
		end_date = self.request.get('end_date')
		
		availability = StarwoodParser.parse_availability(hotel_id, start_date, end_date)
					
		self.response.out.write(simplejson.dumps({'availability': availability}))


def main():
	ROUTES = [
		('/services/availability/(.*)/data.json', HotelAvailability),
		('/services/hotels.json', HotelsLookup),
		('/services/hotels_all.json', AllHotels)
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)


if __name__ == "__main__":
	main()