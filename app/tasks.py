from datetime import date, datetime
import time

from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api.labs import taskqueue
from google.appengine.api.labs.taskqueue import TaskAlreadyExistsError, TombstonedTaskError

from app.parsers import StarwoodParser
from app.models import StarwoodProperty, StarwoodDateAvailability
import app.helper as helper

from lib.dateutil.relativedelta import relativedelta

import logging
logging.getLogger().setLevel(logging.DEBUG)


TASK_QUEUE_PROCESS_AVAILABILITY = "process-starwood-availability"
TASK_NAME_PROCESS_AVAILABILITY = "process-starwood-availability-%d-%s-%04d%02d%02d-%d" #hotel_id, ratecode, year, month, day, epoch

YEAR_MONTH_FORMAT = "%04d-%02d"

class FetchStarwoodAvailability(webapp.RequestHandler):
	@staticmethod
	def enqueue_task(hotel_id=None, ratecode=None, day=None, nights=None, method='GET', writer=logging.info):
		task_params = {'hotel_id': hotel_id, 'ratecode': ratecode, 'date': helper.date_to_str(day)}
		if method == 'GET':
			task_params['nights'] = nights
		task = taskqueue.Task(url='/tasks/availability/process', \
								name=TASK_NAME_PROCESS_AVAILABILITY
										% (hotel_id, ratecode, day.year, \
											day.month, day.day, int(time.time())),
								method=method,
								params=task_params)

		try:
			task.add(TASK_QUEUE_PROCESS_AVAILABILITY)
			writer("Added task '%s' to task queue '%s'.\n" \
					% (task.name, TASK_QUEUE_PROCESS_AVAILABILITY))
			return True
			
		except TaskAlreadyExistsError:
			writer("Task '%s' already exists in task queue '%s'.\n" \
					% (task.name, TASK_QUEUE_PROCESS_AVAILABILITY))
		except TombstonedTaskError:
			writer("Task '%s' is tombstoned in task queue '%s'.\n" \
					% (task.name, TASK_QUEUE_PROCESS_AVAILABILITY))
		
		return False
									
	'''
	/tasks/availability/fetch?hotel_id=232&date=2010-10&ratecode=SPGCP
	'''
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		try:
			hotel_id = int(self.request.get('hotel_id', default_value=''))
		except:
			hotel_id = None
			
		#year_month = self.request.get('date', default_value='')
		start_date = helper.str_to_date(self.request.get('date'))
		months_delta = int(self.request.get('months_delta', default_value=1)) - 1
		end_date = start_date + relativedelta(months=+months_delta)
		ratecode = self.request.get('ratecode', default_value='')
			
		availability_data = None
		if hotel_id and start_date and ratecode:
			try:
				availability_data = StarwoodParser.parse_availability( \
										hotel_id=hotel_id, \
										start_date=YEAR_MONTH_FORMAT % (start_date.year, start_date.month), \
										end_date=YEAR_MONTH_FORMAT % (end_date.year, end_date.month), \
										ratecode=ratecode) \
									.get('availability')
			except:
				pass
				
		if availability_data:
			added_task_count = 0
			
			for year in availability_data:
				for month in availability_data[year]:
					for day, nights_data in availability_data[year][month].iteritems():
						availability_date = date(year=year, month=month, day=day)

						task = taskqueue.Task(url='/tasks/availability/process', \
												name=TASK_NAME_PROCESS_AVAILABILITY \
														% (hotel_id, ratecode, availability_date.year, \
															availability_date.month, availability_date.day, \
															int(time.time())), \
												method='GET', \
												params={'hotel_id': hotel_id, 'ratecode': ratecode, \
														'date': availability_date.strftime("%Y-%m-%d"), \
														'nights': nights_data.keys()})

						try:
							task.add(TASK_QUEUE_PROCESS_AVAILABILITY)
							self.response.out.write("Added task '%s' to task queue '%s'.\n" \
													% (task.name, TASK_QUEUE_PROCESS_AVAILABILITY))
							added_task_count += 1
						except TaskAlreadyExistsError:
							self.response.out.write("Task '%s' already exists in task queue '%s'.\n" \
													% (task.name, TASK_QUEUE_PROCESS_AVAILABILITY))
						except TombstonedTaskError:
							self.response.out.write("Task '%s' is tombstoned in task queue '%s'.\n" \
													% (task.name, TASK_QUEUE_PROCESS_AVAILABILITY))
											
			self.response.out.write("\nAdded %d tasks to the queue.\n" % (added_task_count))

		else:
			self.response.out.write("Invalid request.")
		

class ProcessStarwoodAvailability(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		try:
			hotel_id = int(self.request.get('hotel_id', default_value=''))
		except:
			hotel_id = None

		if hotel_id:
			hotel = StarwoodProperty.get_by_id(hotel_id)
		else:
			hotel = None
			
		try:
			day = date(*(datetime.strptime(self.request.get('date'), "%Y-%m-%d").timetuple()[:3]))
		except:
			day = None
			
		ratecode = self.request.get('ratecode', default_value='').strip()
		nights_list = [int(n) for n in self.request.get_all('nights')]

		if hotel and day and ratecode and nights_list:
			dirty = True
			
			# lookup availability entity for hotel, day, and ratecode
			availability = StarwoodDateAvailability.lookup(hotel, day, ratecode)
			if not availability:
				availability = StarwoodDateAvailability(hotel=hotel, date=day, ratecode=ratecode)
			
			# if the list of nights match, don't update
			if set(availability.nights) == set(nights_list):
				dirty = False

			# if a change exists, insert/update the entity
			if dirty:
				availability.nights = nights_list
				availability.put()
			
			self.response.out.write("%s" % (availability))
			
		else:
			self.response.out.write("Invalid request.")
			
		

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
		('/tasks/availability/process', ProcessStarwoodAvailability),
		('/tasks/availability/fetch', FetchStarwoodAvailability),
		('/tasks/hotel', StarwoodPropertyProcesser),
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)


if __name__ == "__main__":
	main()