import os
import urllib
import random
import datetime
import wsgiref.handlers
from collections import defaultdict

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch

from app import helper
from app.models import StarwoodProperty

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
		
		for hotel in StarwoodProperty.all().filter('location != ', 'NULL'):
			if hotel.location:
				hotel.update_location()
				hotel.put()
			
		self.response.out.write("Updated locations.")


def main():
	ROUTES = [
		('/sandbox/duplicates/(.*)', FindDuplicateHotels),
		('/sandbox/updatelocations', UpdateLocations),
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)


if __name__ == "__main__":
	main()