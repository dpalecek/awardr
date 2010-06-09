import os
import wsgiref.handlers

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch

from app import helper
from app.models import StarwoodProperty

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
		
		
class Home(webapp.RequestHandler):
	def get(self):
		template_values = {}
		self.response.out.write(template.render(helper.get_template_path("index"),
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



def main():
	ROUTES = [
		('/foo', CreateCoord),
		('/starwood/(.*)', StarwoodPropertyView),
		('/starwood', StarwoodPropertiesView),
		('/', Home)
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)


if __name__ == "__main__":
	main()