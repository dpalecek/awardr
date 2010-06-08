from google.appengine.ext import db
from google.appengine.api import memcache

import logging
logging.getLogger().setLevel(logging.DEBUG)


class StarwoodProperty(db.Model):
	id = db.IntegerProperty(required=True)
	name = db.StringProperty(required=True)
	address = db.StringProperty()
	city = db.StringProperty()
	state = db.StringProperty()
	phone = db.PhoneNumberProperty()
	fax = db.PhoneNumberProperty()
	postal_code = db.StringProperty()
	country = db.StringProperty()
	category = db.IntegerProperty(required=True)
	last_checked = db.DateTimeProperty(required=True, auto_now=True)
	
	@staticmethod
	def create(props):
		logging.info("props: %s" % props)
		
		hotel = None
		if 'id' in props and StarwoodProperty.get_by_id(int(props['id'])) is None:
			hotel = StarwoodProperty(id=int(props['id']), name=props['name'], category=int(props['category']))

			addr_props = props['address']
			logging.info("addr_props: %s" % addr_props)
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