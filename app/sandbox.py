import re
import os
import random
import datetime
import wsgiref.handlers
import StringIO
import urllib
import urllib2
import csv
import cookielib


from collections import defaultdict

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch
from google.appengine.api.urlfetch import DownloadError

from app import helper
from app.models import StarwoodProperty, StarwoodDateAvailability, StarwoodSetCode
from app import resources

try: import json
except ImportError: import simplejson as json

from lib.BeautifulSoup import BeautifulSoup as BeautifulSoup
from lib.geomodel import geomodel
from lib.dateutil.relativedelta import relativedelta
from lib import mechanize

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


class HiltonFlex(webapp.RequestHandler):
	def get(self):
		'''
		http://doubletree.hilton.com/en/dt/hotels/index.jhtml;jsessionid=WETF4UTFTLNGYCSGBIY222Q?ctyhocn=CHINPDT
		'''
		hotel_url = "http://doubletree1.hilton.com/en_US/dt/hotel/CHINPDT-theWit-A-Doubletree-Hotel-Illinois/index.do"
		hotel_response = urlfetch.fetch(url=hotel_url)
		
		
class HiltonLogin(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		base_url = "https://secure.hilton.com%s"
		login_landing_url = base_url % "/en/hhonors/login/login.jhtml"
		
		br = mechanize.Browser()
		
		br.set_cookiejar(cookielib.LWPCookieJar())
		br.set_handle_equiv(True)
		br.set_handle_gzip(True)
		br.set_handle_redirect(True)
		br.set_handle_referer(True)
		br.set_handle_robots(False)
		br.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]
		
		br.open("http://doubletree1.hilton.com/en_US/dt/hotel/CHINPDT-theWit-A-Doubletree-Hotel-Illinois/index.do")
		a = br.select_form(name="rewardSearch")
		logging.info("%s" % a)
		br.form.set_all_readonly(False)
		br.form.find_control(name="flexCheckInDay", kind="list").value = ["3"]
		br.form.find_control(name="flexCheckInMonthYr", kind="list").value = ["December 2010"]
		br.form.find_control(name="checkInDay", kind="list").value = ["3"]
		br.form.find_control(name="checkInMonthYr", kind="list").value = ["December 2010"]
		br.form.find_control(name="checkOutDay", kind="list").value = ["5"]
		br.form.find_control(name="checkOutMonthYr", kind="list").value = ["December 2010"]
		br.form.find_control(name="los", kind="list").value = ["2"]
		br.form["isReward"] = "true"
		br.form["flexibleSearch"] = "true"
		br.form["source"] = "hotelResWidget"
		br.submit()
		

		br.select_form(name="loginForm")
		br.form['Username'] = 'mshafrir'
		br.form['password'] = 'Jordan23'
		br.submit()
		
		for form in br.forms():
			self.response.out.write("%s\n\n\n\n\n" % form)
			
		self.response.out.write("\n\n\n\n\n==============\n\n\n\n\n")
		
		'''
		br.select_form(name="loginForm")
		br.form['Username'] = 'mshafrir'
		br.form['password'] = 'Jordan23'
		br.submit()
		'''
		
		


class AllSetCodes(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		prefix_len = len('StarwoodSetCode_')
		setcode_keys = []
		offset = 0
		
		r = db.Query(StarwoodSetCode, keys_only=True).filter('chainwide_rate =', False).filter('chainwide_discount =', False).order('code').fetch(limit=8000, offset=offset)
		setcode_keys.extend(r)
		offset = len(r)				
			
		
		setcode_keys = [int(key.name()[prefix_len:]) for key in setcode_keys]
		self.response.out.write("%s\n\n" % offset)
		self.response.out.write("%s" % json.dumps(setcode_keys))



# /sandbox/setcoderate?hotel_id=1234&set_code=57464
class SetCodeRate(webapp.RequestHandler):
	def get(self):
		def clean_detail(soup):
			return str(' '.join(soup.contents[0].replace('\n', ' ').split()).strip())
			
		def parse_rate_details(rate_row):
			rate_details = {}
			rate_details['bed'] = clean_detail(rate_row.find('td', attrs={'class': 'bedType'}).find('p'))
			rate_details['room'] = clean_detail(rate_row.find('td', attrs={'class': 'roomFeatures'}).find('p'))
			rate_details['rate'] = clean_detail(rate_row.find('td', attrs={'class': 'averageDailyRatePerRoom'}).find('p', attrs={'class': 'roomTotal'}).find('a'))
			
			return rate_details
		
		self.response.headers['Content-Type'] = 'text/plain'
		rate_data = {}

		try:
			set_code = int(self.request.get('set_code', 0))
		except:
			set_code = None

		try:
			hotel_id = int(self.request.get('hotel_id', 0))
		except:
			hotel_id = None

		name = None

		if not (set_code and hotel_id):
			rate_data['error'] = "Required set code and hotel id."
			
		else:
			check_in = datetime.date.today() + relativedelta(months=1)
			check_out = check_in + relativedelta(days=1)
			#url = "https://www.starwoodhotels.com/preferredguest/search/ratelist.html?corporateAccountNumber=%d&lengthOfStay=1&roomOccupancyTotal=001&requestedChainCode=SI&requestedAffiliationCode=SI&theBrand=SPG&submitActionID=search&arrivalDate=2010-09-15&departureDate=2010-09-16&propertyID=%d&ciDate=09/15/2010&coDate=09/19/2010&numberOfRooms=01&numberOfAdults=01&roomBedCode=&ratePlanName=&accountInputField=57464&foo=5232"
			url = "https://www.starwoodhotels.com/preferredguest/search/ratelist.html?arrivalDate=%s&departureDate=%s&corporateAccountNumber=%d&propertyID=%d" \
					% (helper.date_to_str(check_in), helper.date_to_str(check_out), set_code, hotel_id)
			try:
				response = urlfetch.fetch(url, deadline=10)
			except DownloadError, details:
				logging.error("DownloadError: %s" % details)
				response = None

			if response:
				soup = BeautifulSoup(response.content)
				try:
					name = str(soup.find('table', attrs={'id': 'rateListTable'}).find('tbody').find('tr').find('td', attrs={'class': 'rateDescription'}).find('p').contents[0].strip())
				except:
					name = None
				
				rates = [parse_rate_details(lowest_rates.parent.parent) for lowest_rates in soup.findAll('p', attrs={'class': 'roomRate lowestRateIndicator'})]
				rate_data = {'set_code': set_code, 'hotel_id': hotel_id, \
								'check_in': helper.date_to_str(check_in), \
								'check_out': helper.date_to_str(check_out), \
								'rates': rates}
								
		self.response.out.write("%s" % json.dumps(rate_data))



class MechanizeTest(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		br = mechanize.Browser()
		br.open("http://www.example.com/")
		self.response.out.write("title: %s" % br.title())
		
		

def main():
	ROUTES = [
		('/sandbox/mechanize', MechanizeTest),
		('/sandbox/setcoderate', SetCodeRate),
		('/sandbox/setcodes', AllSetCodes),
		('/sandbox/hiltonflex', HiltonFlex),
		('/sandbox/hilton', HiltonLogin),
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