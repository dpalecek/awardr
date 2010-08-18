import os
import urllib
import random
import datetime
import wsgiref.handlers
import StringIO
import urllib2
import csv

from collections import defaultdict

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch

from app import helper
from app.models import StarwoodProperty, StarwoodDateAvailability
from app import resources

try: import json
except ImportError: import simplejson as json

from lib.geomodel import geomodel

import logging
logging.getLogger().setLevel(logging.DEBUG)
		

class RemoveDuplicateHotelAvailabilities(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		try:
			hotel_id = int(self.request.get('hotel_id', 0))
		except:
			hotel_id = 0
			
		if hotel_id:
			hotel = StarwoodProperty.all().filter('id =', hotel_id).get()
		else:
			hotel = StarwoodProperty.random()
			
		self.response.out.write("Hotel: %s\n" % hotel)
		
		if hotel:
			avails_to_del = []
			avail_map = defaultdict(list)
			
			for avail in StarwoodDateAvailability.all().filter('hotel =', hotel):
				avail_map[(avail.hotel.id, avail.ratecode, avail.date)].append(avail)
				
			nights_compare = lambda avail1, avail2: len(avail1.nights) - len(avail2.nights)
			for avails in (avails for avails in avail_map.values() if len(avails) > 1):
				avails.sort(cmp=nights_compare)
				avails_to_del.extend(avails[1:])
				
			self.response.out.write("Found %d duplicates.\n" % len(avails_to_del))
			
			if bool(self.request.get("persist", False)):
				self.response.out.write("Deleting duplicate entities.\n")
				db.delete(avails_to_del[:500])
			else:
				self.response.out.write("Not deleting entities.\n")
			
			if bool(self.request.get("kickoff", False)):
				response = urlfetch.fetch("http://www.awardpad.com/cron/availability?hotel_id=%d" % hotel.id)
				self.response.out.write("\nKicked off availability update task.")
			else:
				self.response.out.write("\nDid not kick off availability update task.")
			

class FindDuplicateHotels(webapp.RequestHandler):
	def get(self, param='phone'):
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.out.write("param: %s\n" % (param))
		
		d = defaultdict(int)
		
		for hotel in StarwoodProperty.all():
			if param == 'phone':
				d[hotel.phone] += 1
			elif param == 'fax':
				d[hotel.fax] += 1
			elif param == 'address':
				d[hotel.address] += 1
			elif param == 'id':
				d[hotel.id] += 1
				
		for k, v in d.iteritems():
			if v > 1:
				self.response.out.write("%s => %s\n" % (k, v))


class UpdateLocations(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		try:
			hotel_id = int(self.request.get('id', default_value=0))
		except:
			hotel_id = 0
			
		if hotel_id:
			msg = "\nHotel location_geocells %s:\n%s\n"
			hotel = StarwoodProperty.all().filter('id =', hotel_id).get()
			self.response.out.write("Hotel: %s\n" % (hotel))
			self.response.out.write(msg % ("before", hotel.location_geocells))
			hotel.update_location()
			hotel.put()
			self.response.out.write(msg % ("after", hotel.location_geocells))
			
		else:
			offset = int(self.request.get('offset', default_value=0))
			limit = int(self.request.get('limit', default_value=100))
		
			for hotel in StarwoodProperty.all().fetch(limit, offset):
				if hotel.location and not hotel.location_geocells:
					self.response.out.write("Updated location for %s.\n" % (hotel))
					hotel.update_location()
					hotel.put()
			
		self.response.out.write("\nUpdated locations.\n")


class ShowAvailability(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		try:
			hotel_id = int(self.request.get('hotel_id', default_value=''))
		except:
			hotel_id = None

		if hotel_id:
			hotel = StarwoodProperty.get_by_id(hotel_id)
		else:
			hotel = None
			
		if hotel:
			self.response.out.write("Hotel: %s\n" % (hotel))
			
			for ratecode in ['SPGCP', 'SPG%d' % (hotel.category)]:
				self.response.out.write("\n\nRatecode: %s\n" % (ratecode))
				for avail in StarwoodDateAvailability.hotel_query(hotel=hotel).filter('ratecode =', ratecode):
					self.response.out.write("\t[%s] %s\t=>\t%s\n" % (avail.key().name(), avail.date, [int(n) for n in avail.nights]))
					



class LoadCoords(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		limit = int(self.request.get('limit', default_value=20))
		
		result = urllib2.urlopen('http://dl.dropbox.com/u/31404/awardpad.csv')
		c_file = StringIO.StringIO(result.read())
		reader = csv.DictReader(c_file)

		coords = {}
		for line in reader:
			id = int(line['id']) #int(line[11])
			try:
				coord = [float(l) for l in line['coord'].strip().split(',')]
				coords[id] = db.GeoPt(*coord)
			except:
				None
			
		for hotel in StarwoodProperty.all().filter('location =', None)[:limit]:
			if hotel.id in coords:
				hotel.location = coords[hotel.id]
				hotel.update_location()
				hotel.put()
			
				self.response.out.write('Updated %s (%s).\n' % (hotel, hotel.location))
			else:
				self.response.out.write('Skipping %s.\n' % (hotel))

			
class ShowCountries(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		countries = {}
		
		for country, id in ((hotel.country, hotel.id) for hotel in StarwoodProperty.all()):
			if not countries.get(country):
				countries[country] = {'count': 0, 'id': int(id)}
			countries[country]['count'] += 1
			
		self.response.out.write("Found %d countries.\n\n" % len(countries))
		
		country_keys = countries.keys()
		country_keys.sort()
		for i, country in enumerate(country_keys):
			if not resources.CURRENCIES.get(country):
				self.response.out.write("%d. %s => %s\n" % (i + 1, country, countries[country]))


def main():
	ROUTES = [
		('/sandbox/remove-duplicate-hotel-availabilities', RemoveDuplicateHotelAvailabilities),
		('/sandbox/countries', ShowCountries),
		('/sandbox/availability', ShowAvailability),
		('/sandbox/duplicates/(.*)', FindDuplicateHotels),
		('/sandbox/updatelocations', UpdateLocations),
		('/sandbox/loadcoords', LoadCoords),
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)


if __name__ == "__main__":
	main()