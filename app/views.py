import os
import urllib
import random
import datetime
import wsgiref.handlers

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch

from app import helper
from app.models import StarwoodProperty
from app.parsers import StarwoodParser

import simplejson

import logging
logging.getLogger().setLevel(logging.DEBUG)


class CreateCoord(webapp.RequestHandler):
	def get(self):
		offset = int(self.request.get("offset", 0))
		self.response.headers['Content-Type'] = 'text/plain'
		for hotel in StarwoodProperty.all().fetch(100, offset):
			if hotel.coord:
				pass
			else:
				self.response.out.write("Reset (%s) %s.\n" % (hotel.id, hotel.name))
				hotel.coord = None
				hotel.save()


def geocoder_service(address):
	url = "http://maps.google.com/maps/api/geocode/json?address=%s&sensor=%s" \
			% (urllib.quote_plus(address), "true")
	response = urlfetch.fetch(url)
	if response.status_code == 200:
		try:
			return simplejson.loads(response.content)['results'][0]['geometry']['location']
		except:
			pass

	return None

class SearchView(webapp.RequestHandler):
	def get(self):
		where = self.request.get('where')
		loc = geocoder_service(where)
		
		try:
			nights = int(self.request.get('nights', 1))
		except:
			nights = 1
		nights = max(min(nights, 5), 1)
		
		today = datetime.date.today()
		
		try:
			day = int(self.request.get('day', today.day))
		except:
			day = today.day
		
		try:
			month = int(self.request.get('month', today.month))
		except:
			month = today.month
		month = max(min(month, 12), 1)
			
		try:
			year = int(self.request.get('year', today.year))
		except:
			year = today.year
		year = max(min(year, today.year + 2), today.year)
		
		template_values = {'where': where, 'year': year, 'month': month, 'day': day, 'nights': nights, \
							'loc': loc}
		self.response.out.write(template.render(helper.get_template_path("search"),
								template_values))
		
		
		
class LandingView(webapp.RequestHandler):
	def get(self):
		DAYS = xrange(1,32)
		MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",)
		all_hotels = StarwoodProperty.all().fetch(2000)
		random.shuffle(all_hotels)
		
		template_values = {'days': DAYS, 'months': MONTHS, 'hotels': all_hotels,}
		self.response.out.write(template.render(helper.get_template_path("landing"),
								template_values))
		
		
class StarwoodPropertyView(webapp.RequestHandler):
	def get(self, id):
		self.response.headers['Content-Type'] = 'text/plain'
		try:
			property_id = int(id)
		except:
			property_id = None
		hotel = StarwoodProperty.all().filter('id =', property_id).get()
		if hotel:
			self.response.out.write("%s" % hotel.props())
		else:
			self.response.out.write("Property with id '%s' not found." % (id))
		
		if self.request.get('geocode', None) == 'true':
			self.response.out.write("\n\ngeocoded: %s" % hotel.geocode())
			
		'''
		foo = urlfetch.fetch(url='http://www.hilton.com/en/dt/hotels/search/hotelResWidgetFromPFS.jhtml?checkInDay=1&checkInMonthYr=September+2010&checkOutDay=2&checkOutMonthYr=September+2010&flexCheckInDay=1&flexCheckInMonthYr=September+2010&los=1&ctyhocn=CHINPDT&isReward=true&flexibleSearch=false', deadline=10)
		if foo and foo.final_url:
			pass #foo = urlfetch.fetch(foo.final_url)
		self.response.out.write("\n%s" % foo.final_url)
		self.response.out.write("\n%s" % foo.status_code)
		self.response.out.write("\n%s" % foo.headers['set-cookie'].split(';')[0])
		self.response.out.write("\n\n%s" % foo.content)
		'''
		
		
class StarwoodPropertiesView(webapp.RequestHandler):
	def get(self):
		template_values = {}
		
		hotels = StarwoodProperty.all().order('id')
		category = int(self.request.get("category", 0))
		if category:
			hotels = hotels.filter('category =', category)
		
		template_values['hotels'] = hotels
		self.response.out.write(template.render(helper.get_template_path("starwood"),
								template_values))



class RateLookupView(webapp.RequestHandler):
	def get(self):
		night = datetime.date.today() #+ datetime.timedelta(days=30)
		template_values = {'date': "%d-%02d-%02d" % (night.year, night.month, night.day)}
			
		self.response.out.write(template.render(helper.get_template_path("ratelookup"),
								template_values))
								
	def post(self):
		# ratecode param
		ratecode = self.request.get('ratecode', default_value='').strip().upper()
		if not (ratecode and len(ratecode)):
			ratecode = 'RACK'
		
		# hotel param
		try:
			hotel_id = int(self.request.get('hotel_id', default_value="-1").strip())
		except:
			hotel_id = None
			
		if hotel_id:
			hotel = StarwoodProperty.get_by_id(id=hotel_id)
			
		if not hotel_id:
			hotel_name = self.request.get('hotel', default_value='').strip()
			
			# try to look up the hotel based on name
			if hotel_name and len(hotel_name):
				hotel = StarwoodProperty.get_by_prop(prop='name', value='hotel_name')
			else:
				hotel = None
				
			# just pick a random hotel if no hotel id or name specified
			if not hotel:
				hotel = StarwoodProperty.random()
				
			hotel_id = hotel.id
		
		# data param
		date = self.request.get('date', default_value='').strip()
		try:
			year, month, day = [int(p) for p in date.split('-')]
		except:
			today = datetime.date.today()
			date = "%d-%02d-%02d" % (today.year, today.month, today.day)
			year, month, day = [int(p) for p in date.split('-')]
		
		
		template_values = {'ratecode': ratecode, 'hotel_id': hotel_id, 'hotel': hotel, \
							'date': date, 'submitted': True}
		
		if ratecode and hotel_id and date:
			
			date_ym = "%d-%02d" % (year, month)
			avail_data = StarwoodParser.parse_availability(hotel_id=hotel_id, ratecode=ratecode, \
																start_date=date_ym, end_date=date_ym)

			try:
				night = avail_data['availability'][year][month][day][1]
			except:
				night = None
			
			template_values['found'] = night is not None
			if night:
				template_values['currency_code'] = avail_data['currency_code']
				template_values['rate'] = night['rate']
				template_values['points'] = night['pts']

		self.response.out.write(template.render(helper.get_template_path("ratelookup"),
								template_values))


def main():
	ROUTES = [
		('/rate-lookup', RateLookupView),
		('/search', SearchView),
		('/foo', CreateCoord),
		('/starwood/(.*)', StarwoodPropertyView),
		('/starwood', StarwoodPropertiesView),
		('/', LandingView),
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)


if __name__ == "__main__":
	main()