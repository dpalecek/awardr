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

import simplejson
from lib.geomodel import geomodel

import logging
logging.getLogger().setLevel(logging.DEBUG)


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
		
		offset = int(self.request.get('offset', default_value=0))
		limit = int(self.request.get('limit', default_value=100))
		
		for hotel in StarwoodProperty.all().fetch(limit, offset):
			if hotel.location and not hotel.location_geocells:
				self.response.out.write("Updated location for %s.\n" % (hotel))
				hotel.update_location()
				hotel.put()
			
		self.response.out.write("Updated locations.\n")


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
					self.response.out.write("\t%s\t=>\t%s\n" % (avail.date, [int(n) for n in avail.nights]))
					



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
			

def main():
	ROUTES = [
		('/sandbox/availability', ShowAvailability),
		('/sandbox/duplicates/(.*)', FindDuplicateHotels),
		('/sandbox/updatelocations', UpdateLocations),
		('/sandbox/loadcoords', LoadCoords),
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)


if __name__ == "__main__":
	main()