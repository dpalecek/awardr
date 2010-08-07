from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

from app.parsers import StarwoodParser
from app.models import StarwoodProperty, StarwoodPropertyCounter

import logging
logging.getLogger().setLevel(logging.DEBUG)

class StarwoodPropertyProcesser(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		prop_id = int(self.request.get('prop_id', 0))
		brand = self.request.get('brand')
		
		if prop_id:
			hotel_props = StarwoodParser.parse(prop_id)
			if hotel_props:
				hotel_props.update({'brand': brand})
				logging.info("Property id %s => %s" % (prop_id, hotel_props))
				self.response.out.write("Property id %s => %s\n\n" % (prop_id, hotel_props))

				hotel = StarwoodProperty.create(hotel_props)
				if hotel:
					logging.info("Created hotel!")
				else:
					logging.info("Failed to create hotel!")
					
				self.response.out.write("Found prop id %s? %s" \
						% (prop_id, StarwoodProperty.get_by_id(prop_id) is not None))
			else:
				self.response.out.write("Did not find prop id %d." % (prop_id))


def main():
	ROUTES = [
		('/tasks/hotel', StarwoodPropertyProcesser)
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)


if __name__ == "__main__":
	main()