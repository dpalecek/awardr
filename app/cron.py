import os
import wsgiref.handlers
import random

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import urlfetch
from google.appengine.api.labs import taskqueue
from google.appengine.api.labs.taskqueue import TaskAlreadyExistsError, TombstonedTaskError

from app.parsers import StarwoodParser
from app.models import StarwoodProperty, StarwoodPropertyCounter

from lib.BeautifulSoup import BeautifulSoup
import simplejson

import logging
logging.getLogger().setLevel(logging.DEBUG)

LIMIT = 200
TASK_QUEUE = "starwood-properties"


class GeocodeProperty(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		hotels = StarwoodProperty.all().filter('coord =', None).fetch(1000)
		
		if hotels and len(hotels):
			random.shuffle(hotels)
			hotel = hotels[0]
		else:
			hotel = None
			
		if hotel:
			self.response.out.write("%s left.\n" % len(hotels))
			self.response.out.write("%s %s\n%s => %s" % (hotel.id, hotel.name, hotel.full_address(), hotel.geocode()))
		else:
			self.response.out.write("All hotels are geocoded.")


class FetchProperty(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		start_prop_id = int(self.request.get("prop_id", 0))
		if not start_prop_id:
			start_prop_id = StarwoodPropertyCounter.get_and_increment(LIMIT)
			
		if start_prop_id < 300000:
			task_name = "starwood-property-%d"
			for prop_id in xrange(start_prop_id, start_prop_id + LIMIT):
				task = taskqueue.Task(url='/tasks/property', params={'prop_id': prop_id}, \
										name=task_name % prop_id, method='GET')
				try:
					task.add(TASK_QUEUE)
					self.response.out.write("Added task '%s' to task queue '%s'.\n" % (task.name, TASK_QUEUE))
				except TaskAlreadyExistsError:
					self.response.out.write("Task '%s' already exists in task queue '%s'.\n" % (task.name, TASK_QUEUE))
				except TombstonedTaskError:
					self.response.out.write("Task '%s' is tombstoned in task queue '%s'.\n" % (task.name, TASK_QUEUE))
				
				#self.response.out.write("Could not add task '%s'.\n" % (task.name))


class FetchDirectory(webapp.RequestHandler):
	def get(self, category_id=1):
		def is_valid_property(d):
			return d['class'].find('newProperty') == -1 and info_div.find('a', 'propertyName') is not None
		
		self.response.headers['Content-Type'] = 'text/plain'
	
		directory_ids = []
	
		directory_url = "https://www.starwoodhotels.com/corporate/directory/hotels/all/list.html?categoryFilter=%s" % int(category_id)
		directory_response = urlfetch.fetch(url=directory_url, deadline=10)
		
		if directory_response and directory_response.status_code == 200:
			soup = BeautifulSoup(directory_response.content)
			for link in [info_div.find('a', 'propertyName') for info_div in soup.findAll('div', 'propertyInfo') if is_valid_property(info_div)]:
				directory_ids.append(int(link['href'].split('propertyID=')[1])) #a['href'].split('?')[1].split('&')
		
		diff_ids = list(frozenset(directory_ids) - frozenset([hotel.id for hotel in StarwoodProperty.all()]))
		diff_ids.sort()

		if diff_ids and len(diff_ids):		
			task_name = "starwood-property-%d"
			for prop_id in diff_ids:
				task = taskqueue.Task(url='/tasks/property', params={'prop_id': prop_id}, \
										name=task_name % prop_id, method='GET')
				try:
					task.add(TASK_QUEUE)
					self.response.out.write("Added task '%s' to task queue '%s'.\n" % (task.name, TASK_QUEUE))
				except TaskAlreadyExistsError:
					self.response.out.write("Task '%s' already exists in task queue '%s'.\n" % (task.name, TASK_QUEUE))
				except TombstonedTaskError:
					self.response.out.write("Task '%s' is tombstoned in task queue '%s'.\n" % (task.name, TASK_QUEUE))
		else:
			self.response.out.write("No new hotels found in category %s." % (category_id))
	

class CheckAvailability(webapp.RequestHandler):
	def get(self, hotel_id=None):
		self.response.headers['Content-Type'] = 'text/plain'
		
		found = False
		
		if hotel_id:
			date = self.request.get('date')
			year, month, day = [str(int(d)) for d in date.split('-')]
			days = int(self.request.get('days', 1))
			
			hotel_availability_url = 'http://awardr.appspot.com/services/availability/%s/data.json' % (int(hotel_id))
			hotel_availability_response = urlfetch.fetch(url=hotel_availability_url, deadline=10)
			if hotel_availability_response and hotel_availability_response.status_code == 200:
				hotel_availability = simplejson.loads(hotel_availability_response.content)['availability']
				try:
					if days in hotel_availability[year][month][day]:
						found = True
				except:
					found = False
					
		self.response.out.write("Found? %s" % found)
		

def main():
	ROUTES = [
		('/cron/availability/(.*)', CheckAvailability),
		('/cron/directory/(.*)', FetchDirectory),
		('/cron/geocode', GeocodeProperty),
		('/cron/property', FetchProperty)
	]

	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)

    
if __name__ == "__main__":
    main()