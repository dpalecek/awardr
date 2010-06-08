import os
import wsgiref.handlers

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.api import urlfetch

from app import helper
from app.models import StarwoodProperty

import logging
logging.getLogger().setLevel(logging.DEBUG)


class Home(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.out.write("Home")
		
class StarwoodProperties(webapp.RequestHandler):
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
		('/starwood', StarwoodProperties),
		('/', Home)
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)


if __name__ == "__main__":
	main()