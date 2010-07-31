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

import simplejson
from lib.BeautifulSoup import BeautifulSoup as BeautifulSoup

import logging
logging.getLogger().setLevel(logging.DEBUG)



starwood_url = 'https://www.starwoodhotels.com/preferredguest/search/ratelist.html'

class StarwoodParser(webapp.RequestHandler):
	@staticmethod
	def parse_availability(hotel_id, start_date, end_date, ratecode='SPGCP'):
		'''
		?start=2010-06&end=2010-07&hotel_id=1021&ratecode=BAR1
		'''
		
		availability = {}
		
		url = "http://vendoori.com/roomaward/data.json?start=%s&end=%s&hotel_id=%s&ratecode=%s" \
					% (start_date, end_date, hotel_id, ratecode)
		response = urlfetch.fetch(url=url, #"http://www.starwoodhotels.com/corporate/checkAvail.do?startMonth=%s&endMonth=%s&ratePlan=%s&propertyId=%s" % (start_date, end_date, "SPGCP", hotel_id),
										deadline=10)
		if response and response.status_code == 200:
			availability_data = simplejson.loads(response.content)['data']
			currency_code = availability_data['currencyCode']
			
			available_dates = availability_data['availDates']
			if available_dates:
				for year_month_key in available_dates:
					year, month = [int(p) for p in year_month_key.split('-')]
					if not year in availability:
						availability[year] = {}

					month_data = {}
					for year_month_day_key in available_dates[year_month_key]:
						day_data = available_dates[year_month_key][year_month_day_key]
						day_key = int(year_month_day_key.split('-')[-1])
						month_data[day_key] = {}
						for rate in [{int(key): day_data[key]} for key in day_data.keys()]:
							month_data[day_key].update(rate)
				
					availability[year][month] = month_data
					
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
		hotel_props = {}
		
		today = datetime.date.today()
		tomorrow = today + datetime.timedelta(days=1)
		date_format = "%s-%02d-%02d"
		
		arrival_date = date_format % (today.year, today.month, today.day)
		departure_date = date_format % (tomorrow.year, tomorrow.month, tomorrow.day)
		starwood_response = urlfetch.fetch(url='%s?arrivalDate=%s&departureDate=%s&propertyID=%s' % (starwood_url, arrival_date, departure_date, property_id),
											deadline=10)
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
		
		ratecode = self.request.get('ratecode', default_value='SPGCP')
		
		hotel_props = StarwoodParser.parse(property_id, ratecode)
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