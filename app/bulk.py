from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.api import urlfetch
from google.appengine.ext.webapp.util import run_wsgi_app

from app.models import StarwoodProperty

import simplejson


class DownloadBulk(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'application/json'
		self.response.out.write(simplejson.dumps( \
			{'hotels': [hotel.props() for hotel in StarwoodProperty.all()]}))


class UploadBulk(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		hotels_data = None
		
		if self.request.get("reset") == "true":
			db.delete(StarwoodProperty.all().fetch(1000))
		
		source_url = self.request.get('source_url')
		if source_url:
			source_response = urlfetch.fetch(source_url)
			if source_response and source_response.status_code == 200:
				hotels_data = simplejson.loads(source_response.content)['hotels']
					
		counter = 0
		
		if hotels_data and len(hotels_data):
			hotel_ids = [int(hotel.id) for hotel in StarwoodProperty.all()]
			for hotel_data in hotels_data:
				hotel_id = int(hotel_data['id'])
				if hotel_id not in hotel_ids:
					hotel = StarwoodProperty(id=hotel_id,
												name=hotel_data['name'],
												category=hotel_data['category'])
					try:
						hotel.address = hotel_data['address']
					except:
						pass
					try:
						hotel.city = hotel_data['city']
					except:
						pass
					try:
						hotel.state = hotel_data['state']
					except:
						pass
					try:
						hotel.postal_code = hotel_data['postal_code']
					except:
						pass
					try:
						hotel.country = hotel_data['country']
					except:
						pass
					try:
						hotel.phone = hotel_data['phone']
					except:
						pass
					try:
						hotel.fax = hotel_data['fax']
					except:
						pass
					try:
						hotel.coord = db.GeoPt(lat=hotel_data['coord']['lat'], lon=hotel_data['coord']['lng'])
					except:
						pass
						
					hotel.put()
					counter += 1
		
		self.response.out.write("Created %s hotels." % counter)


def main():
	ROUTES = [
		('/bulk/upload', UploadBulk),
		('/bulk/hotels.json', DownloadBulk),
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)


if __name__ == "__main__":
	main()