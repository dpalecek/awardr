from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import urlfetch

import app.helper as helper

import urllib
import random

import simplejson

import logging
logging.getLogger().setLevel(logging.DEBUG)


CATEGORY_AWARD_CHOICES = {
	'cash_points': {
		1: {'points': 1200, 'cash': 25,},
		2: {'points': 1600, 'cash': 30,},
		3: {'points': 4000, 'cash': 45,},
		4: {'points': 4000, 'cash': 60,},
		5: {'points': 4800, 'cash': 90,},
		6: {'points': 8000, 'cash': 150,},
	},
	'points': {
		1: {'points': 3000},
		2: {'points': 4000},
		3: {'points': 7000},
		4: {'points': 10000},
		5: {'points': 12000},
		6: {'points': 20000},
		7: {'points': 30000},
	},
}

STARWOOD_BRANDS = [
	"westin", "sheraton", "fourpoints", "whotels", "lemeridien", "stregis", "luxury", "alofthotels", "element"
]


class StarwoodProperty(db.Model):
	id = db.IntegerProperty(required=True)
	name = db.StringProperty(required=True)
	category = db.IntegerProperty(required=True)
	brand = db.StringProperty(choices=STARWOOD_BRANDS)
	
	address = db.StringProperty()
	city = db.StringProperty()
	state = db.StringProperty()
	postal_code = db.StringProperty()
	country = db.StringProperty()
	
	coord = db.GeoPtProperty()
	
	phone = db.PhoneNumberProperty()
	fax = db.PhoneNumberProperty()
	
	#http://www.starwoodhotels.com/pub/media/1445/wes1445ex.60365_tn.jpg
	#http://www.starwoodhotels.com/pub/media/1445/wes1445ex.60365_md.jpg
	#http://www.starwoodhotels.com/pub/media/1445/wes1445ex.60365_lg.jpg
	image_url = db.LinkProperty()
	
	last_checked = db.DateTimeProperty(required=True, auto_now=True)
	
	def props(self):
		props = {'id': int(self.id), \
					'name': helper.remove_accents(self.name), \
					'category': int(self.category), \
					'address': helper.remove_accents(self.address), \
					'city': helper.remove_accents(self.city), \
					'state': helper.remove_accents(self.state),
					'postal_code': helper.remove_accents(self.postal_code), \
					'country': helper.remove_accents(self.country),
					'phone': str(self.phone), 'fax': str(self.fax)}
		if self.coord:
			props['coord'] = {'lat': self.coord.lat, 'lng': self.coord.lon}
		return props
	
	def encoded_full_address(self):
		return self.full_address(encoded=True)
		
	def full_address(self, encoded=False):
		full_address = helper.remove_accents("%s %s %s %s %s" % (self.address, self.city or "", self.state or "", self.postal_code or "", self.country))
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
			if 'image_url' in props:
				hotel.image_url = props['image_url']
			if 'brand' in props:
				hotel.brand = props['brand']

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
		 	hotel = StarwoodProperty.all().filter('id =', id).get()
		else:
			hotel = None
		
		return hotel

	@staticmethod
	def get_by_prop(prop=None, value=None):
		if prop and value:
			hotel = StarwoodProperty.all().filter('%s =' % (prop), value).get()
		else:
			hotel = None

		return hotel

	@staticmethod
	def random():
		hotel = random.choice(StarwoodProperty.all().fetch(2000))
		return hotel
	
	@staticmethod
	def all_cache():
		hotels = memcache.get('hotels')
		if not hotels:
			hotels = StarwoodProperty.all()
			memcache.set('hotels', hotels)
		
		return hotels
		

class StarwoodPropertyDateAvailability(db.Model):
	hotel = db.ReferenceProperty(StarwoodProperty, required=True)
	date = db.DateProperty(required=True)
	nights = db.ListProperty(long)
	
	last_checked = db.DateTimeProperty(required=True, auto_now=True)


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