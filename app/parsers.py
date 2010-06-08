import os
import wsgiref.handlers

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.api import urlfetch

import app.helper as helper

#import simplejson
from lib.BeautifulSoup import BeautifulSoup as BeautifulSoup

#from templatefilters import *
#webapp.template.register_template_library('templatefilters')

from google.appengine.api import urlfetch

import logging
logging.getLogger().setLevel(logging.DEBUG)

starwood_url = 'https://www.starwoodhotels.com/preferredguest/search/ratelist.html'



class StarwoodParser(webapp.RequestHandler):
	@staticmethod
	def parse_starwood(soup):
		def parse_points(soup):
			try:
				return {'points': int(soup.find('span', 'starpoints').contents[0])}
			except:
				return None

		def parse_cashpoints(soup):
			try:
				cp = {}
				cp['points'] = int(soup.find('span', 'cashPoints').contents[0])
				cp['cash'] = int(soup.find('span', 'cashPointsMessage').contents[0].split(' ')[-1])
				return cp
			except:
				return None

		return [parse_points(soup[1]), parse_cashpoints(soup[2])]

	@staticmethod
	def parse_address(soup):
		address = {}
		address_container_soup = soup.find("div", "addressContainer")
		address['address1'] = unicode(address_container_soup.find("div", "address1").contents[0])

		for part in ["city", "state", "zipCode", "country"]:
			try:
				val = unicode(address_container_soup.find("span", part).contents[0])
				if val.endswith(','):
					val = val[:-1]
				address[part] = val
			except:
				pass

		for phone_key in ['phone', 'fax']:
			try:
				address[phone_key] = ' '.join(str(address_container_soup.find("span", "%sNumber" % phone_key).contents[0]).split()[1:])
			except:
				pass

		return address
	
	
	@staticmethod
	def parse(property_id):
		valid_property = False
		hotel_props = {}
		
		start_date, departure_date = '2010-06-29', '2010-06-30'
		starwood_response = urlfetch.fetch('%s?arrivalDate=%s&departureDate=%s&propertyID=%s' % (starwood_url, start_date, departure_date, property_id))
		if starwood_response:
			soup = BeautifulSoup(starwood_response.content)
			if soup:
				try:
					hotel_props['name'] = unicode(soup.find("a", "propertyName").contents[0]).strip()
					hotel_props['category'] = int(str(soup.find("span", "spgCategory").contents[0]).split()[-1])

					valid_property = True
				except:
					pass
					
				if valid_property:
					hotel_props['id'] = property_id
					hotel_props['address'] = StarwoodParser.parse_address(soup)
					hotel_props['awards'] = StarwoodParser.parse_starwood(soup.find("div", "tabsContentContainer").findAll("div", "tabContent"))
		
		if valid_property and len(hotel_props):
			return hotel_props
		else:
			return None
		
		
	def get(self, property_id=None):
		self.response.headers['Content-Type'] = 'text/plain'
		
		hotel_props = StarwoodParser.parse(property_id)

		if hotel_props:
			self.response.out.write("%s" % hotel_props)
		if not hotel_props:
			msg = "Property not found or error parsing."
			self.response.out.write(msg)
			self.response.set_status(code=500, message=msg)


def main():
	ROUTES = [
		('/property/starwood/(.*)', StarwoodParser)
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)


if __name__ == "__main__":
	main()