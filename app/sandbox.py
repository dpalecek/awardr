import re
import os
import random
import datetime
import wsgiref.handlers
import StringIO
import urllib
import urllib2
import csv

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
		base_url = "https://secure.hilton.com%s"
		login_landing_url = base_url % "/en/hhonors/login/login.jhtml"
		self.response.headers['Content-Type'] = 'text/plain'
		
		response = urlfetch.fetch(url=login_landing_url)
		session_cookie = response.headers.get('Set-Cookie').split(';')[0]
		self.response.out.write("session_cookie: %s\n" % session_cookie)
		loginForm = BeautifulSoup(response.content).find('form', attrs={'name': 'loginForm'})
		action_url = base_url % loginForm.get("action")
		self.response.out.write("action: %s\n\n" % action_url)
		
		params = {"Username": "mshafrir", "password": "Jordan23"}
		for inputEl in loginForm.findAll('input'):
			if inputEl.get('value'):
				params[inputEl.get("name")] = inputEl.get("value")
		
		form_data = urllib.urlencode(params)
		form_data = "%2Fcom%2Fhilton%2Fcrm%2Fclient%2Fhandler%2FLoginFormHandler.repeat=0&_D%3A%2Fcom%2Fhilton%2Fcrm%2Fclient%2Fhandler%2FLoginFormHandler.repeat=+&%2Fcom%2Fhilton%2Fcrm%2Fclient%2Fhandler%2FLoginFormHandler.repeatErrorURL=%2Fen%2Fhhonors%2Fhelp%2Fsign_in_help.jhtml&_D%3A%2Fcom%2Fhilton%2Fcrm%2Fclient%2Fhandler%2FLoginFormHandler.repeatErrorURL=+&prevPageTitle=Login+Page&%2Fcom%2Fhilton%2Fcrm%2Fclient%2Fhandler%2FLoginFormHandler.successURL=%2Fen%2Fhhonors%2Fmytravelplanner%2Fmy_account.jhtml&_D%3A%2Fcom%2Fhilton%2Fcrm%2Fclient%2Fhandler%2FLoginFormHandler.successURL=+&%2Fcom%2Fhilton%2Fcrm%2Fclient%2Fhandler%2FLoginFormHandler.successURL=%2Fen%2Fhhonors%2Fmytravelplanner%2Fmy_account.jhtml&_D%3A%2Fcom%2Fhilton%2Fcrm%2Fclient%2Fhandler%2FLoginFormHandler.successURL=+&%2Fcom%2Fhilton%2Fcrm%2Fclient%2Fhandler%2FLoginFormHandler.failureURL=%2Fen%2Fhhonors%2Flogin%2Flogin.jhtml&_D%3A%2Fcom%2Fhilton%2Fcrm%2Fclient%2Fhandler%2FLoginFormHandler.failureURL=+&Username=mshafrir&_D%3AUsername=+&password=Jordan23&_D%3Apassword=+&_D%3ArememberUser=+&%2Fcom%2Fhilton%2Fcrm%2Fclient%2Fhandler%2FLoginFormHandler.submit.x=8&%2Fcom%2Fhilton%2Fcrm%2Fclient%2Fhandler%2FLoginFormHandler.submit.y=12&_D%3A%2Fcom%2Fhilton%2Fcrm%2Fclient%2Fhandler%2FLoginFormHandler.submit=+&brandCode=HH&joinHHonorsURL=%2Fen%2Fhhonors%2Fsignup%2Fhhonors_enroll.jhtml&sessionExchangePrefix=http%3A%2F%2Fhhonors1.hilton.com&page_width=784px&align=left&isStaticMasthead=true&show_signin=false"
		self.response.out.write("form_data: %s\n\n" % form_data)
		
		response = urlfetch.fetch(url=action_url, deadline=10, method=urlfetch.POST, payload=form_data, follow_redirects=False, \
					headers={'Content-Type': 'application/x-www-form-urlencoded', 'Referer': 'https://secure.hilton.com/en/hhonors/login/login.jhtml', 'Cookie': session_cookie})
		logged_in_url = base_url % response.headers.get('location').split('?')[0]
		session_id = logged_in_url.split(';')[1].split('=')[1]
		
		self.response.out.write("logged_in_url: %s" % logged_in_url)
		
		self.response.out.write("\n\n=====================\n\n")
		
		logged_in_response = urlfetch.fetch(url=logged_in_url, deadline=10, method=urlfetch.GET, follow_redirects=False, \
												headers={'Cookie': session_cookie})

		hotel_url = "http://doubletree.hilton.com/en/dt/hotels/index.jhtml;jsessionid=%s?ctyhocn=CHINPDT" % (session_id)
		self.response.out.write("getting: %s" % hotel_url) 
		#http://doubletree.hilton.com/en/dt/hotels/index.jhtml;jsessionid=WETF4UTFTLNGYCSGBIY222Q?ctyhocn=CHINPDT
		resp = urlfetch.fetch(url= hotel_url, method=urlfetch.GET, follow_redirects=True)
		if resp:
			self.response.out.write("\nfinal_url: %s\n" % resp.final_url)
			self.response.out.write("headers: %s\n" % resp.headers)



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
			self.response.out.write("Require set code and hotel id.\n")
			
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

				self.response.out.write("name: %s\n" % name)
				self.response.out.write("rates: %s" % rates)



def main():
	ROUTES = [
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