import os
import wsgiref.handlers
import datetime

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.api import urlfetch

import app.helper as helper
import app.resources as resources

try: import json
except ImportError: import simplejson as json

from lib.BeautifulSoup import BeautifulSoup as BeautifulSoup

import logging
logging.getLogger().setLevel(logging.DEBUG)

starwood_url = 'https://www.starwoodhotels.com/preferredguest/search/ratelist.html'

class StarwoodParser(webapp.RequestHandler):
	@staticmethod
	def mod_spg_points(category, day):
		is_weekend = 4 <= datetime.date.weekday(day) <= 5
		return {'points': resources.CATEGORY_AWARD_CHOICES['points'][category][is_weekend]['min'], \
				'rate': None}
		
	@staticmethod
	def is_spg_points_rate(ratecode):
		import re
		return re.match('^SPG[1-7]$', ratecode) is not None
		
		
	@staticmethod
	def parse_currency(hotel_id=None):
		if hotel_id:
			starwood_url = "http://www.starwoodhotels.com/corporate/checkAvail.do?propertyId=%s&ratePrefValue=%s&ratePref=ratePlanId&numberOfRooms=1&numberOfAdults=1" % (hotel_id, 'RACK')
			response = urlfetch.fetch(url=starwood_url, deadline=10)
			if response and response.status_code == 200:
				try:
					return json.loads(response.content)['data']['currencyCode']
				except:
					pass
		
		return None
		
	
	@staticmethod
	def parse_availability(hotel_id, start_date, end_date=None, ratecode='SPGCP'):
		def get_currency_code(d):
			logging.error("d: %s" % d)
			logging.info("foo: %s" % type(d))
			while True:
				if type(d) == type({}):
					if not d.has_key('curr'):
						logging.info("get next d")
						d = d.get(d.keys()[0])
					else:
						logging.info("return the curr")
						return d.get('curr')
				else:
					logging.info("not a dict, quit")
					break
			
			logging.info("Returned nothing")
			return None
		
		from app.models import StarwoodProperty
		
		if not end_date:
			end_date = start_date
		'''
		?start=2010-06&end=2010-07&hotel_id=1021&ratecode=BAR1
		'''
		
		hotel = StarwoodProperty.get_by_id(id=hotel_id)
		if not hotel:
			return None
			
		else:
			availability = {}

			starwood_url = "http://www.starwoodhotels.com/corporate/checkAvail.do?startMonth=%s&endMonth=%s&propertyId=%s&ratePrefValue=%s&ratePref=ratePlanId&numberOfRooms=1&numberOfAdults=1"
			#vendoori_url = "http://vendoori.com/roomaward/data.json?start=%s&end=%s&hotel_id=%s&ratecode=%s"
			url = starwood_url % (start_date, end_date, hotel_id, ratecode)
			
			response = urlfetch.fetch(url=url, deadline=10)
			if response and response.status_code == 200:
				availability_data = json.loads(response.content).get('data')
				
				#currency_code = availability_data.get('currencyCode')
				currency_code = get_currency_code(availability_data)
				logging.error("%s" % currency_code)
			
				available_dates = availability_data.get('availDates')
				if available_dates:
					for year_month_key in available_dates:
						year, month = [int(p) for p in year_month_key.split('-')]
						availability.setdefault(year, {})
						
						month_data = {}
						for year_month_day_key in available_dates[year_month_key]:
							day_data = available_dates[year_month_key][year_month_day_key]
							day_key = int(year_month_day_key.split('-')[-1])
							day_date = datetime.date(year, month, day_key)
							
							month_data[day_key] = {}
							for night, rate_data in day_data.iteritems():
								night = int(night)
								if StarwoodParser.is_spg_points_rate(ratecode):
									rate_data = StarwoodParser.mod_spg_points(hotel.category, day_date + datetime.timedelta(days=night))
									
								month_data[day_key][night] = rate_data

						availability[int(year)][int(month)] = month_data
					
			else:
				currency_code = None
	
			return {'currency_code': currency_code, 'availability': availability}
	
	
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
		try:
			address['address2'] = unicode(address_container_soup.find("div", "address2").contents[0])
		except:
			pass

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
	def parse(property_id, ratecode='SPGCP'):
		valid_property = False
		hotel_props = {'id': property_id}
		
		starwood_response = urlfetch.fetch(url='%s?propertyID=%s' % (starwood_url, property_id),
											deadline=10)
		if starwood_response:
			try:
				soup = BeautifulSoup(starwood_response.content).find(attrs={'id': 'propertyHighlight'}).find(attrs={'class': 'propertyContainer'})
			except:
				soup = None
			
			if soup:
				try:
					hotel_props['name'] = unicode(soup.find("a", "propertyName").contents[0]).strip()
					hotel_props['category'] = int(str(soup.find("span", "spgCategory").contents[0]).split()[-1])

					valid_property = True
				except:
					pass
					
				if valid_property:
					hotel_props['address'] = StarwoodParser.parse_address(soup)
					#hotel_props['awards'] = StarwoodParser.parse_starwood(soup.find("div", "tabsContentContainer").findAll("div", "tabContent"))
					hotel_props['image_url'] = str("http://www.starwoodhotels.com%s" % (soup.find("img", "propertyThumbnail")['src']))
		
		return valid_property and hotel_props or None
		
		
	def get(self, hotel_id=None):
		hotel_id = int(hotel_id)
		self.response.headers['Content-Type'] = 'text/plain'
		
		ratecode = self.request.get('ratecode', default_value='SPGCP')
		start_date = self.request.get('start')
		end_date = self.request.get('end')
		
		if start_date and end_date:
			self.response.out.write( \
				json.dumps( \
					StarwoodParser.parse_availability(hotel_id, start_date, end_date, ratecode)))
			
		else:
			hotel_props = StarwoodParser.parse(hotel_id, ratecode)
			if hotel_props:
				self.response.out.write("%s" % hotel_props)
			if not hotel_props:
				msg = "Property not found or error parsing."
				self.response.out.write(msg)
				self.response.set_status(code=500, message=msg)


def main():
	ROUTES = [
		('/property/starwood/(.*)', StarwoodParser),
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)


if __name__ == "__main__":
	main()