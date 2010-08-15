import datetime
import time
import random

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.api import users
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import urlfetch
from google.appengine.api import mail
from google.appengine.api.labs import taskqueue
from google.appengine.api.labs.taskqueue import TaskAlreadyExistsError, TombstonedTaskError

from app.parsers import StarwoodParser
from app.models import StarwoodProperty, StarwoodDateAvailability
import app.helper as helper

from lib.BeautifulSoup import BeautifulSoup
from lib.dateutil.relativedelta import relativedelta
import simplejson

import logging
logging.getLogger().setLevel(logging.DEBUG)


TASK_QUEUE_PROCESS_HOTEL = "starwood-properties"
TASK_NAME_PROCESS_HOTEL = "starwood-hotel-%d-%d"

TASK_QUEUE_FETCH_AVAILABILITY = "fetch-starwood-availability"
TASK_NAME_FETCH_AVAILABILITY = "fetch-starwood-availability-%d-%s-%04d%02d-%02d-%d" #hotel_id, ratecode, start_date, delta
DATE_FORMAT = "%04d-%02d"
MONTHS_DELTA = 12
YEARS_FUTURE = 1


class GeocodeProperty(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		try:
			hotel_id = int(self.request.get('id', default_value=0))
		except:
			hotel_id = 0
		
		hotels = StarwoodProperty.all().filter('location =', None)
		if hotels and hotels.count():
			if hotel_id:
				hotel = hotels.filter('id =', hotel_id).get()
			else:
				hotel = random.choice(hotels.fetch(2000))
		else:
			hotel = None
			
		if hotel:
			coord, status = hotel.geocode()
			self.response.out.write("%d left.\n" % (hotels.count()))
			self.response.out.write("Geocoder status: %s\n" % (status))
			self.response.out.write("Hotel id %d: %s\n%s => %s" % \
					(hotel.id, helper.remove_accents(hotel.name), \
						helper.remove_accents(hotel.full_address()), \
						coord))
		else:
			self.response.out.write("All hotels are geocoded.")


class FetchDirectory(webapp.RequestHandler):
	def get(self, category_id=1):
		def is_valid_property(d):
			return d['class'].find('newProperty') == -1 and info_div.find('a', 'propertyName') is not None
		
		self.response.headers['Content-Type'] = 'text/plain'
	
		directory_hotels = {}
	
		directory_url = "https://www.starwoodhotels.com/corporate/directory/hotels/all/list.html?categoryFilter=%s" % int(category_id)
		directory_response = urlfetch.fetch(url=directory_url, deadline=10)
		
		if directory_response and directory_response.status_code == 200:
			soup = BeautifulSoup(directory_response.content)
			for link in [info_div.find('a', 'propertyName') for info_div in soup.findAll('div', 'propertyInfo') if is_valid_property(info_div)]:
				hotel_url = link['href']
				logging.info("hotel_url: %s" % hotel_url)
				directory_hotels[int(hotel_url.split('propertyID=')[1])] = str(hotel_url.split('/')[1]) #a['href'].split('?')[1].split('&')
		
		diff_ids = list(frozenset(directory_hotels.keys()) - frozenset([hotel.id for hotel in StarwoodProperty.all()]))
		diff_ids.sort()
		
		added_task_count = 0

		if diff_ids and len(diff_ids):	
			for prop_id in diff_ids:
				task = taskqueue.Task(url='/tasks/hotel', \
										name=TASK_NAME_PROCESS_HOTEL % (prop_id, datetime.datetime.now().microsecond), \
										method='GET', \
										params={'prop_id': prop_id, 'brand': directory_hotels[prop_id]})
				try:
					task.add(TASK_QUEUE_PROCESS_HOTEL)
					self.response.out.write("Added task '%s' to task queue '%s'.\n" % (task.name, TASK_QUEUE_PROCESS_HOTEL))
					added_task_count += 1
				except TaskAlreadyExistsError:
					self.response.out.write("Task '%s' already exists in task queue '%s'.\n" % (task.name, TASK_QUEUE_PROCESS_HOTEL))
				except TombstonedTaskError:
					self.response.out.write("Task '%s' is tombstoned in task queue '%s'.\n" % (task.name, TASK_QUEUE_PROCESS_HOTEL))
			
			self.response.out.write("\nAdded %d tasks to the queue.\n" % (added_task_count))
			
		else:
			self.response.out.write("No new hotels found in category %s." % (category_id))


class HotelAvailabilityStarter(webapp.RequestHandler):
	def get(self):
		months_delta = int(self.request.get('months', 1))
		
		self.response.headers['Content-Type'] = 'text/plain'
		
		try:
			hotel_id = int(self.request.get('hotel_id'))
		except:
			hotel_id = None
		
		hotels = StarwoodProperty.all()
		if hotel_id:
			hotel = hotels.filter('id =', hotel_id).get()
		else:
			hotel = hotels.order('last_checked').get()
			
		if not hotel:
			self.response.out.write("Did not get a hotel.\n")
			
		else:
			self.response.out.write("Got hotel %s [%s].\n" % (hotel.name, hotel.id))
			added_task_count = 0
			
			for ratecode in ['SPGCP', 'SPG%d' % (hotel.category)]:
				start_date = datetime.date.today()
				end_date = start_date + relativedelta(years=YEARS_FUTURE)
				
				while start_date < end_date:
					task = taskqueue.Task(url='/tasks/availability/fetch', \
											name=TASK_NAME_FETCH_AVAILABILITY \
													% (hotel.id, ratecode, start_date.year, \
														start_date.month, MONTHS_DELTA, int(time.time())), \
											method='GET', \
											params={'hotel_id': hotel.id, 'ratecode': ratecode, \
													'date': DATE_FORMAT % (start_date.year, start_date.month), \
													'months_delta': MONTHS_DELTA})

					try:
						task.add(TASK_QUEUE_FETCH_AVAILABILITY)
						self.response.out.write("Added task '%s' to task queue '%s'.\n" \
												% (task.name, TASK_QUEUE_FETCH_AVAILABILITY))
						added_task_count += 1
					except TaskAlreadyExistsError:
						self.response.out.write("Task '%s' already exists in task queue '%s'.\n" \
												% (task.name, TASK_QUEUE_FETCH_AVAILABILITY))
					except TombstonedTaskError:
						self.response.out.write("Task '%s' is tombstoned in task queue '%s'.\n" \
												% (task.name, TASK_QUEUE_FETCH_AVAILABILITY))
												
					start_date += relativedelta(months=MONTHS_DELTA)
			
			hotel.put()



class CronExpireAvailability(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		try:
			limit = int(self.request.get('limit', default_value=100))
		except:
			limit = 100
			
		past_dates = StarwoodDateAvailability.all().filter('date <', datetime.date.today()).fetch(limit)
		self.response.out.write("Deleting %d expired entries:\n" % len(past_dates))
		for p in past_dates:
			self.response.out.write("\t%s\n" % p)

		db.delete(past_dates)
		
		
		
class CronRefreshHotelInfo(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		try:
			hotel_id = int(self.request.get('hotel_id'))
		except:
			hotel_id = None
		
		hotels = StarwoodProperty.all()
		if hotel_id:
			hotel = hotels.filter('id =', hotel_id).get()
		else:
			logging.info(hotels.count())
			hotel = hotels.filter('currency =', None).get() #order('last_refreshed').get()
		
		if hotel:
			info = StarwoodParser.parse(hotel.id)
			'''
			for d in ['category', 'image_url', ]
			category = info.get('category')
			if category:
				hotel.category = category
			phone = info.get('phone')
			'''
			
		self.response.out.write('%s' % parsed)
	


def main():
	ROUTES = [
		('/cron/refresh-hotel', CronRefreshHotelInfo),
		('/cron/expire', CronExpireAvailability),
		('/cron/availability', HotelAvailabilityStarter),
		('/cron/directory/(.*)', FetchDirectory),
		('/cron/geocode', GeocodeProperty),
		#('/cron/property', FetchProperty)
	]

	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)

    
if __name__ == "__main__":
    main()