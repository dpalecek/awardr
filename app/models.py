from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import urlfetch

import urllib

import simplejson

import logging
logging.getLogger().setLevel(logging.DEBUG)


CATEGORY_CNP_CHOICES = {
	1: {'cash': 25,		'points': 1200},
	2: {'cash': 30,		'points': 1600},
	3: {'cash': 45,		'points': 4000},
	4: {'cash': 60,		'points': 4000},
	5: {'cash': 90,		'points': 4800},
	6: {'cash': 150,	'points': 8000},
	#7: {'cash': 90,		'points': 4800},
}

class StarwoodProperty(db.Model):
	id = db.IntegerProperty(required=True)
	name = db.StringProperty(required=True)
	category = db.IntegerProperty(required=True)
	
	address = db.StringProperty()
	city = db.StringProperty()
	state = db.StringProperty()
	postal_code = db.StringProperty()
	country = db.StringProperty()
	
	coord = db.GeoPtProperty()
	
	phone = db.PhoneNumberProperty()
	fax = db.PhoneNumberProperty()
	
	last_checked = db.DateTimeProperty(required=True, auto_now=True)
	
	def props(self):
		props = {'id': self.id, 'name': self.name, 'category': self.category,
					'address': self.address, 'city': self.city, 'state': self.state,
					'postal_code': self.postal_code, 'country': self.country,
					'phone': self.phone, 'fax': self.fax}
		if self.coord:
			props['coord'] = {'lat': self.coord.lat, 'lng': self.coord.lon}
		return props
	
	def encoded_full_address(self):
		return self.full_address(encoded=True)
		
	def full_address(self, encoded=False):
		full_address = "%s %s %s %s %s" % (self.address, self.city or "", self.state or "", self.postal_code or "", self.country)
		if encoded:
			return urllib.quote_plus(full_address.encode('utf-8'))
		else:
			return full_address
		
	def geocode(self):
		coord = None
		
		geocoder_url = "http://maps.google.com/maps/api/geocode/json?address=%s&sensor=false" % self.encoded_full_address()
		try:
			geocoder_response = urlfetch.fetch(geocoder_url)
			if geocoder_response and geocoder_response.status_code == 200:
				geocoded = simplejson.loads(geocoder_response.content)
				if geocoded['status'] == "OK" and len(geocoded['results']):
					coord = geocoded['results'][0]['geometry']['location']
		except:
			pass
				
		if coord:
			self.coord = coord = db.GeoPt(lat=coord['lat'], lon=coord['lng'])
			self.save()

		return coord
	
	@staticmethod
	def create(props):
		hotel = None
		if 'id' in props and StarwoodProperty.get_by_id(int(props['id'])) is None:
			hotel = StarwoodProperty(id=int(props['id']), name=props['name'], category=int(props['category']))

			addr_props = props['address']
			if 'address1' in addr_props:
				hotel.address = addr_props['address1']
			if 'city' in addr_props:
				hotel.city = addr_props['city']
			if 'state' in addr_props:
				hotel.state = addr_props['state']
			if 'zipCode' in addr_props:
				hotel.postal_code = addr_props['zipCode']
			if 'country' in addr_props:
				hotel.country = addr_props['country']
			if 'phone' in addr_props:
				hotel.phone = addr_props['phone']
			if 'fax' in addr_props:
				hotel.fax = addr_props['fax']

			hotel.put()
			
		return (hotel is not None)
	
	@staticmethod
	def get_by_id(id=None):
		if id:
		 	prop = StarwoodProperty.all().filter('id =', id).get()
		else:
			prop = None
		
		return prop


class StarwoodPropertyDate(db.Model):
	hotel = db.ReferenceProperty(StarwoodProperty, required=True)
	date = db.DateProperty(required=True)


class StarwoodPropertyCounter(db.Model):
	count = db.IntegerProperty(required=True)
	
	@staticmethod
	def get_and_increment(inc_amt=10):
		try:
			counter = StarwoodPropertyCounter.all().get()
		except:
			counter = None
			
		if not counter:
			counter = StarwoodPropertyCounter(count=0)
			counter.put()

		counter.count += inc_amt
		counter.put()
		
		return counter.count - inc_amt