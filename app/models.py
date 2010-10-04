from __future__ import division

import urllib
import random
import datetime

from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import urlfetch

from app.parsers import StarwoodParser
import app.helper as helper
import app.resources as resources

try: import json
except ImportError: import simplejson as json

from lib.geomodel import geomodel
from lib.dateutil.relativedelta import relativedelta

import logging
logging.getLogger().setLevel(logging.DEBUG)




STARWOOD_BRANDS = [
	"westin", "sheraton", "fourpoints", "whotels", "lemeridien", "stregis", "luxury", "alofthotels", "element"
]

STARWOOD_RATECODES = [
	'SPGCP', 'SPG1', 'SPG2', 'SPG3', 'SPG4', 'SPG5', 'SPG6', 'SPG7',
]

CURRENCY_CHOICES = []


class GeocodedLocation(geomodel.GeoModel):
	query = db.StringProperty(required=True)
	count = db.IntegerProperty(required=True, default=1)
	
	@staticmethod
	def mod_query(q):
		return ' '.join(helper.remove_accents(q).strip().split()).replace(',','').lower()
	
	@staticmethod
	def getter(q):
		g = GeocodedLocation.all().filter('query =', GeocodedLocation.mod_query(q)).get()
		if g:
			g.count += 1
			g.put()
			
			return g.location
		
		return None
		
	@staticmethod
	def setter(q, coord):
		if q and coord:
			geo_loc = GeocodedLocation(query=GeocodedLocation.mod_query(q), location=coord)
			geo_loc.update_location()
			geo_loc.put()
		
			return geo_loc
			
		return None


class StarwoodProperty(geomodel.GeoModel):
	id = db.IntegerProperty(required=True)
	name = db.StringProperty(required=True)
	category = db.IntegerProperty(required=True)
	brand = db.StringProperty(choices=STARWOOD_BRANDS)
	
	address = db.StringProperty()
	address2 = db.StringProperty()
	city = db.StringProperty()
	state = db.StringProperty()
	postal_code = db.StringProperty()
	country = db.StringProperty()
	
	phone = db.PhoneNumberProperty()
	fax = db.PhoneNumberProperty()
	
	#http://www.starwoodhotels.com/pub/media/1445/wes1445ex.60365_tn.jpg
	#http://www.starwoodhotels.com/pub/media/1445/wes1445ex.60365_md.jpg
	#http://www.starwoodhotels.com/pub/media/1445/wes1445ex.60365_lg.jpg
	image_url = db.LinkProperty()
	
	currency = db.StringProperty() #CURRENCY_CHOICES)
	
	added = db.DateTimeProperty(auto_now_add=True)
	last_checked = db.DateTimeProperty(auto_now=True)
	
	
	def __str__(self):
		return "%s (%d)" % (helper.remove_accents(self.name), self.id)
		
	def permalink(self):
		permalink = "/hotel/starwood/%d/%s" % (self.id, helper.slugify(self.name))
		logging.info("%s" % permalink)
		return permalink
	
	@classmethod
	def calc_key_name(cls, id=None):
		return "%s_%d" % (cls.kind(), id)
	
	def props(self, props_filter=None):
		props = {'id': int(self.id), \
					'name': helper.remove_accents(self.name), \
					'category': int(self.category), \
					'address': helper.remove_accents(self.address), \
					'address2': helper.remove_accents(self.address2), \
					'city': helper.remove_accents(self.city), \
					'state': helper.remove_accents(self.state),
					'postal_code': helper.remove_accents(self.postal_code), \
					'country': helper.remove_accents(self.country),
					'phone': str(self.phone), 'fax': str(self.fax), \
					'brand': str(self.brand), 'image_url': str(self.image_url)}
		if self.location:
			props['coord'] = {'lat': self.location.lat, 'lng': self.location.lon}

		if props_filter:
			return dict((k,v) for k,v in props.iteritems() if k in props_filter)
		else:
			return props
	
	def html_address(self):
		patterns = ["<span class=\"address_part\">%s</span>\n", \
					"<span class=\"address_part\">%s, %s %s %s</span>\n"]
		if self.address2:
			address_contents = ("%s%s%s" % (patterns[0], patterns[0], patterns[1])) \
					% (self.address, self.address2, self.city, self.state, self.country, self.postal_code)
		else:
			address_contents = ("%s%s" % (patterns[0], patterns[1])) \
					% (self.address, self.city, self.state, self.country, self.postal_code)
		
		return "<address>\n%s</address>\n" % address_contents
	
	def html_short_address(self):
		address = "<address>%s, %s</address>\n" % (self.state and (self.city, self.state) or (self.city, self.country))
		return address
	
	def encoded_full_address(self, with_address2=True):
		return self.full_address(encoded=True, with_address2=with_address2)
		
	def full_address(self, encoded=False, with_address2=True):
		if with_address2:
			full_address = helper.remove_accents("%s %s %s %s %s %s" % (self.address, self.address2 or "", self.city or "", self.state or "", self.postal_code or "", self.country))
		else:
			full_address = helper.remove_accents("%s %s %s %s %s" % (self.address, self.city or "", self.state or "", self.postal_code or "", self.country))
		
		full_address = ' '.join(full_address.split())
		if encoded:
			return urllib.quote_plus(full_address.encode('utf-8'))
		else:
			return full_address
	
	def image(self, size='small'):
		size_map = {'small': 'tn', 'medium': 'md', 'large': 'lg'}
		image_url = self.image_url.replace('_tn.jpg', '_%s.jpg' % size_map.get(size))
		logging.info("%s" % image_url)
		return image_url

	def image_medium(self):
		return self.image(size='medium')
	
	def image_large(self):
		return self.image(size='large')
		
	def geocode(self):
		coord = None
		status = None
		
		geocoder_url = "http://maps.google.com/maps/api/geocode/json?address=%s&sensor=%s" \
							% (self.encoded_full_address(with_address2=False), "false")
		try:
			geocoder_response = urlfetch.fetch(geocoder_url)
			if geocoder_response and geocoder_response.status_code == 200:
				geocoded = json.loads(geocoder_response.content)
				status = geocoded['status']
				if status == "OK" and len(geocoded['results']):
					coord = geocoded['results'][0]['geometry']['location']
		except:
			pass
				
		if coord:
			self.location = db.GeoPt(lat=coord['lat'], lon=coord['lng'])
			self.update_location()
			self.put()

		return coord, status
				
	
	@staticmethod
	def create(props):
		hotel = None
		hotel_id = int(props.get('id'))
		if StarwoodProperty.get_by_id(id=hotel_id) is None:
			hotel = StarwoodProperty(key_name=StarwoodProperty.calc_key_name(hotel_id), \
										id=hotel_id, name=props.get('name'),
										category=int(props.get('category')))
			hotel.image_url = props.get('image_url')
			hotel.brand = props.get('brand')

			addr_props = props.get('address')
			if addr_props:
				hotel.address = addr_props.get('address1')
				hotel.address2 = addr_props.get('address2')
				hotel.city = addr_props.get('city')
				hotel.state = addr_props.get('state')
				hotel.postal_code = addr_props.get('zipCode')
				hotel.country = addr_props.get('country')
				hotel.phone = addr_props.get('phone')
				hotel.fax = addr_props.get('fax')

			hotel.put()
			
		return (hotel is not None)
		
	@staticmethod
	def get_by_id(id=None):
		return id and StarwoodProperty.all().filter('id =', int(id)).get() or None

	@staticmethod
	def get_by_prop(prop=None, value=None):
		return prop and value and StarwoodProperty.all().filter('%s =' % (prop), value).get() or None

	@staticmethod
	def random():
		return random.choice(StarwoodProperty.all().fetch(2000))
	
	@staticmethod
	def all_cache():
		hotels = memcache.get('hotels')
		if not hotels:
			hotels = StarwoodProperty.all()
			memcache.set('hotels', hotels)
		
		return hotels
		

class StarwoodDateAvailability(db.Model):
	hotel = db.ReferenceProperty(StarwoodProperty, required=True, collection_name="hotel_set")
	date = db.DateProperty(required=True)
	ratecode = db.StringProperty(choices=STARWOOD_RATECODES, required=True)
	nights = db.ListProperty(int, required=True)
	
	last_checked = db.DateTimeProperty(required=True, auto_now=True)
	
	def __str__(self):
		return "%s (%d): %s & %s => %s" \
				% (self.hotel.name, self.hotel.id, self.date, self.ratecode, self.nights)
					
	@classmethod
	def calc_key_name(cls, hotel, ratecode, date):
		return "%s_%d-%s-%s" % (cls.kind(), hotel.id, ratecode.upper(), helper.date_to_str(date))

	@staticmethod
	def create(hotel, ratecode, date):
		key_name = StarwoodDateAvailability.calc_key_name(hotel, ratecode, date)
		return StarwoodDateAvailability(key_name=key_name, hotel=hotel, date=date, ratecode=ratecode)
	
	@staticmethod
	def lookup(hotel=None, date=None, ratecode=None):
		if hotel and date and ratecode:
			return StarwoodDateAvailability.all().filter('hotel =', hotel).filter('date =', date).filter('ratecode =', ratecode).get()
			
		return None
		
	@staticmethod
	def hotel_query(hotel=None):
		if hotel:
			return StarwoodDateAvailability.all().filter('hotel =', hotel).order('date')
			
		return None
		
	def expand(self, nights_count=0):
		rate_data = []
		points = cash = 0
		for night in xrange(nights_count):
			date = self.date + relativedelta(days=night)
			if self.ratecode == 'SPGCP':
				rate = resources.CATEGORY_AWARD_CHOICES['cash_points'].get(int(self.hotel.category))
			elif StarwoodParser.is_spg_points_rate(self.ratecode):
				rate = StarwoodParser.mod_spg_points(self.hotel.category, date)
			
			if rate:
				rate_data.append({'date': date, 'rate': rate})
				points += rate.get('points', 0)
				cash += rate.get('cash', 0)
		
		# 5th night free in category 3 and up
		if nights_count == 5 and self.hotel.category >= 3 and StarwoodParser.is_spg_points_rate(self.ratecode):
			points = int(points * 4 / 5)
		
		return {'check_in': self.date, 'check_out': self.date + relativedelta(days=nights_count), \
					'rates': rate_data, 'totals': {'points': points, 'cash': cash}}
					

class StarwoodRatecode(db.Model):
	ratecode = db.StringProperty(required=True)
	added = db.DateTimeProperty(auto_now_add=True)
	#touched
	
	@classmethod
	def calc_key_name(cls, ratecode=None):
		return "%s_%s" % (cls.kind(), ratecode.upper())
		
		
		
class StarwoodSetCodeCounter(db.Model):
	code = db.IntegerProperty(required=True, default=1)
	
	@classmethod
	def calc_key_name(cls):
		return "%s" % (cls.kind())
		
	@staticmethod
	def lookup():
		return StarwoodSetCodeCounter.get_by_key_name(StarwoodSetCodeCounter.calc_key_name())
		
	@staticmethod
	def create():
		counter = StarwoodSetCodeCounter(key_name=StarwoodSetCodeCounter.calc_key_name(), code=1)
		counter.put()
		return counter
	
	@staticmethod
	def increment(inc=100):
		counter = StarwoodSetCodeCounter.lookup()
		if not counter:
			counter = StarwoodSetCodeCounter.create()
			
		counter.code += inc
		counter.put()
	
	@staticmethod
	def current():
		counter = StarwoodSetCodeCounter.lookup()
		if counter:
			return counter.code
		else:
			return 1
						
		

class StarwoodSetCode(db.Model):
	code = db.IntegerProperty(required=True)
	name = db.StringProperty(required=True)
	chainwide_discount = db.BooleanProperty(required=False, default=False)
	chainwide_rate = db.BooleanProperty(required=False, default=False)
	added = db.DateTimeProperty(auto_now_add=True)

	@classmethod
	def calc_key_name(cls, code=None):
		return "%s_%d" % (cls.kind(), code)
		
	@staticmethod
	def create(code=None, name=None):
		if code and name:
			set_code_entity = StarwoodSetCode(key_name=StarwoodSetCode.calc_key_name(code), \
												code=code, name=name, \
												chainwide_discount=(name == "Chainwide Discount"), \
												chainwide_rate=(name == "Chainwide Rate"))
			set_code_entity.put()
			return set_code_entity
			
		return None

class StarwoodSetCodeLookup(db.Model):
	hotel_id = db.IntegerProperty(required=True)
	set_code = db.IntegerProperty(required=True)
	check_in = db.DateProperty(required=True)
	check_out = db.DateProperty(required=True)
	#beds = db.
	
class StarwoodRateLookup(db.Model):
	hotel = db.ReferenceProperty(StarwoodProperty, required=True)
	ratecode = db.ReferenceProperty(StarwoodRatecode, required=True, collection_name="ratecode_set")
	date = db.DateProperty(required=True)
	cash = db.FloatProperty()
	points = db.IntegerProperty()
	
	added = db.DateTimeProperty(auto_now_add=True)
	touched = db.DateTimeProperty(auto_now=True)
	
	@classmethod
	def calc_key_name(cls, hotel, ratecode, date):
		return "%s_%d-%s-%s" % (cls.kind(), hotel.id, ratecode.upper(), helper.date_to_str(date))

	@staticmethod
	def create(hotel, ratecode_entity, date):
		key_name = StarwoodRateLookup.calc_key_name(hotel, ratecode_entity.ratecode, date)
		starwood_ratecode_lookup = StarwoodRatecodeLookup(key_name=key_name, hotel=hotel, ratecode=ratecode_entity, date=date)
		starwood_ratecode_lookup.put()