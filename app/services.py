import os
import wsgiref.handlers

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch

from app import helper
from app.models import StarwoodProperty

import simplejson

import logging
logging.getLogger().setLevel(logging.DEBUG)

def in_viewport(coord, sw, ne):
	return coord.lat >= min(sw['lat'], ne['lat']) and coord.lat <= max(sw['lat'], ne['lat']) \
			and coord.lon >= min(sw['lng'], ne['lng']) and coord.lon <= max(sw['lng'], ne['lng'])

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
		
		hotels = [hotel for hotel in StarwoodProperty.all().filter('coord !=', None)]
		
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
		
		months = {}
		
		data_response = urlfetch.fetch("https://www.starwoodhotels.com/corporate/checkAvail.do?startMonth=%s&endMonth=%s&ratePlan=%s&propertyId=%s" % (start_date, end_date, "SPGCP", hotel_id))
		if data_response and data_response.status_code == 200:
			available_dates = simplejson.loads(data_response.content)['data']['availDates']
			if available_dates:
				for month in available_dates:
					month_key = month #frozenset([int(p) for p in month.split('-')])
					month_data = {}
					
					for day in available_dates[month]:
						month_data[int(day.split('-')[-1])] = [int(key) for key in available_dates[month][day].keys()]
				
					months[month_key] = month_data
					
		self.response.out.write(simplejson.dumps({'months': months}))


def main():
	ROUTES = [
		('/services/availability/(.*)/data.json', HotelAvailability),
		('/services/hotels.json', HotelsLookup)
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)


if __name__ == "__main__":
	main()