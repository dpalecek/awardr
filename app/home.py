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

def parse_address(soup):
	address = {}
	address_container_soup = soup.find("div", "addressContainer")	
	logging.info("%s" % address_container_soup.prettify())
	address['address1'] = address_container_soup.find("div", "address1").contents[0]
	
	for part in ["city", "state", "zipCode", "country"]:
		try:
			address[part] = address_container_soup.find("span", part).contents[0]
		except:
			pass

	try:
		address['phone'] = ' '.join(address_container_soup.find("span", "phoneNumber").contents[0].split()[1:])
	except:
		pass
		
	try:
		address['fax'] = ' '.join(address_container_soup.find("span", "phoneNumber").contents[0].split()[1:])
	except:
		pass

	return address

class StarwoodParser(webapp.RequestHandler):
	def get(self, property_id):
		start_date, departure_date = '2010-06-29', '2010-06-30'
		starwood_response = urlfetch.fetch('%s?arrivalDate=%s&departureDate=%s&propertyID=%s' % (starwood_url, start_date, departure_date, property_id))
		if starwood_response:
			soup = BeautifulSoup(starwood_response.content)
			if soup:
				prop = {}
				prop['name'] = soup.find("a", "propertyName").contents[0].strip()
				prop['address'] = parse_address(soup)
				prop['category'] = soup.find("span", "spgCategory").contents[0].split()[-1]
				awards = parse_starwood(soup.find("div", "tabsContentContainer").findAll("div", "tabContent"))
				self.response.out.write("%s => %s" % (prop, awards))
			else:
				self.response.out.write("none")
			
		self.response.headers['Content-Type'] = 'text/plain'
		'''
        self.response.out.write(template.render(helper.get_template_path("home"),\
                                                template_values))
		'''


def main():
	ROUTES = [
		('/hotel/(.*)', StarwoodParser)
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)


if __name__ == "__main__":
	main()