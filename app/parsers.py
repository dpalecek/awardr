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
from app.models import StarwoodProperty

import simplejson
from lib.BeautifulSoup import BeautifulSoup as BeautifulSoup

import logging
logging.getLogger().setLevel(logging.DEBUG)



starwood_url = 'https://www.starwoodhotels.com/preferredguest/search/ratelist.html'

CAT_POINTS = {
	1: [{'min': 3000, 'max': 3000}, {'min': 2000, 'max': 2000}],
	2: [{'min': 4000, 'max': 4000}, {'min': 3000, 'max': 3000}],
	3: [{'min': 7000, 'max': 7000}, {'min': 7000, 'max': 7000}],
	4: [{'min': 10000, 'max': 10000}, {'min': 10000, 'max': 10000}],
	5: [{'min': 12000, 'max': 16000}, {'min': 12000, 'max': 16000}],
	6: [{'min': 20000, 'max': 25000}, {'min': 20000, 'max': 25000}],
	7: [{'min': 30000, 'max': 35000}, {'min': 30000, 'max': 35000}],
}

class StarwoodParser(webapp.RequestHandler):
	@staticmethod
	def mod_spg_points(rate, category, year_month_day):
		day = datetime.date(*[int(p) for p in year_month_day.split('-')])
		is_weekend = datetime.date.weekday(day) in (4,5)
		for key in rate:
			rate[key] = {'pts': CAT_POINTS[category][is_weekend]['min'], 'rate': None}
		return rate
		
	@staticmethod
	def is_spg_points_rate(ratecode):
		import re
		return re.match('SPG[1-7]', ratecode) is not None
	
	@staticmethod
	def parse_availability(hotel_id, start_date, end_date, ratecode='SPGCP'):
		'''
		?start=2010-06&end=2010-07&hotel_id=1021&ratecode=BAR1
		'''
		
		hotel = StarwoodProperty.get_by_id(id=hotel_id)
		
		if not hotel:
			return None
			
		else:
			availability = {}

			starwood_url = "http://www.starwoodhotels.com/corporate/checkAvail.do?startMonth=%s&endMonth=%s&propertyId=%s&ratePlan=%s"
			vendoori_url = "http://vendoori.com/roomaward/data.json?start=%s&end=%s&hotel_id=%s&ratecode=%s"
			url = starwood_url % (start_date, end_date, hotel_id, ratecode)
			response = urlfetch.fetch(url=url, deadline=10)
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
								if StarwoodParser.is_spg_points_rate(ratecode):
									rate = StarwoodParser.mod_spg_points(rate, hotel.category, year_month_day_key)
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
		hotel_props = {}
		
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
					hotel_props['id'] = property_id
					hotel_props['address'] = StarwoodParser.parse_address(soup)
					#hotel_props['awards'] = StarwoodParser.parse_starwood(soup.find("div", "tabsContentContainer").findAll("div", "tabContent"))
					hotel_props['image_url'] = str("http://www.starwoodhotels.com%s" % (soup.find("img", "propertyThumbnail")['src']))
		
		if valid_property and len(hotel_props):
			return hotel_props
		else:
			return None
		
		
	def get(self, hotel_id=None):
		hotel_id = int(hotel_id)
		self.response.headers['Content-Type'] = 'text/plain'
		
		ratecode = self.request.get('ratecode', default_value='SPGCP')
		start_date = self.request.get('start')
		end_date = self.request.get('end')
		
		if start_date and end_date:
			self.response.out.write( \
				simplejson.dumps( \
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