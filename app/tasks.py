from datetime import date, datetime
import time
import re

from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import urlfetch
from google.appengine.api.urlfetch import DownloadError
from google.appengine.api.labs import taskqueue
from google.appengine.api.labs.taskqueue import TaskAlreadyExistsError, TombstonedTaskError

from app.parsers import StarwoodParser
from app.models import StarwoodProperty, StarwoodDateAvailability, StarwoodSetCode, StarwoodSetCodeRate
import app.helper as helper
import app.helper_starwood as helper_starwood

from lib.BeautifulSoup import BeautifulSoup as BeautifulSoup
from lib.dateutil.relativedelta import relativedelta

try: import json
except ImportError: import simplejson as json

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
		months_delta = int(self.request.get('months_delta', default_value=1))
		end_date = start_date + relativedelta(months=months_delta)
		ratecode = self.request.get('ratecode', default_value='')
			
		availability_data = None
		if hotel_id and start_date and ratecode:
			try:
				availability_data = StarwoodParser.parse_availability( \
										hotel_id=hotel_id,
										start_date=YEAR_MONTH_FORMAT % (start_date.year, start_date.month),
										end_date=YEAR_MONTH_FORMAT % (end_date.year, end_date.month),
										ratecode=ratecode) \
									.get('availability')
			except:
				pass
				
		if availability_data:
			added_task_count = 0
			
			all_days = []
			d = date.today() + relativedelta(days=0)
			while d < end_date:
				all_days.append(d)
				d += relativedelta(days=1)
			
			for year in availability_data:
				for month in availability_data[year]:
					for day, nights_data in availability_data[year][month].iteritems():
						availability_date = date(year=year, month=month, day=day)
						if availability_date in all_days:
							all_days.remove(availability_date)

						success = FetchStarwoodAvailability.enqueue_task( \
										hotel_id=hotel_id, ratecode=ratecode,
										day=availability_date, nights=nights_data.keys(),
										writer=self.response.out.write)
						if success:
							added_task_count += 1
											
			self.response.out.write("\nAdded %d tasks to the queue.\n" % (added_task_count))
			
			
			# Delete the entities that don't have availability.
			for day in all_days:
				FetchStarwoodAvailability.enqueue_task(hotel_id=hotel_id, ratecode=ratecode, \
														day=day, method='DELETE',
														writer=self.response.out.write)

		else:
			self.response.out.write("Invalid request.")
		

class ProcessStarwoodAvailability(webapp.RequestHandler):
	def delete(self):
		try:
			hotel_id = int(self.request.get('hotel_id', default_value=''))
		except:
			hotel_id = None

		if hotel_id:
			hotel = StarwoodProperty.get_by_id(hotel_id)
		else:
			hotel = None
			
		try:
			day = helper.str_to_date(self.request.get('date'))
		except:
			day = None
		
		ratecode = self.request.get('ratecode', default_value='').strip()
		
		availability = StarwoodDateAvailability.lookup(hotel, day, ratecode)
		if availability:
			db.delete(availability)
			
		
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
			day = helper.str_to_date(self.request.get('date'))
		except:
			day = None
			
		ratecode = self.request.get('ratecode', default_value='').strip()
		nights_list = [int(n) for n in self.request.get_all('nights')]

		if hotel and day and ratecode:
			dirty = True
			
			# lookup availability entity for hotel, day, and ratecode
			availability = StarwoodDateAvailability.lookup(hotel, day, ratecode)
			if not availability:
				availability = StarwoodDateAvailability.create(hotel=hotel, date=day, ratecode=ratecode)
			
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



class SetCodeLookupTask(webapp.RequestHandler):
	def get(self):
		def valid_setcode(soup):
			try:
				top_msg_div = soup.find('div', attrs={'id': 'topMsgDiv'})
				if top_msg_div.find('span', attrs={'class': 'error'}) and bool(top_msg_div.find('p').contents[0].strip()):
					return False
				else:
					return True
			except:
				return True


		self.response.headers['Content-Type'] = 'text/plain'

		try:
			set_code = int(self.request.get('set_code', 0))
		except:
			set_code = None
		if StarwoodSetCode.get_by_key_name(StarwoodSetCode.calc_key_name(set_code)):
			self.response.out.write("SET code entity already created.")
			return

		try:
			hotel_id = int(self.request.get('hotel_id', 0))
		except:
			hotel_id = None

		name = None

		if set_code and hotel_id:
			check_in = date.today() + relativedelta(months=1)
			check_out = check_in + relativedelta(days=1)
			#url = "https://www.starwoodhotels.com/preferredguest/search/ratelist.html?corporateAccountNumber=%d&lengthOfStay=1&roomOccupancyTotal=001&requestedChainCode=SI&requestedAffiliationCode=SI&theBrand=SPG&submitActionID=search&arrivalDate=2010-09-15&departureDate=2010-09-16&propertyID=%d&ciDate=09/15/2010&coDate=09/19/2010&numberOfRooms=01&numberOfAdults=01&roomBedCode=&ratePlanName=&accountInputField=57464&foo=5232"
			url = "https://www.starwoodhotels.com/preferredguest/search/ratelist.html?arrivalDate=%s&departureDate=%s&corporateAccountNumber=%d&propertyID=%d" \
					% (helper.date_to_str(check_in), helper.date_to_str(check_out), set_code, hotel_id)
			try:
				response = urlfetch.fetch(url, deadline=10)
			except DownloadError, details:
				logging.error("DownloadError: %s" % details)
				response = None

			if response:
				soup = BeautifulSoup(response.content)
				if valid_setcode(soup):
					try:
						name = str(soup.find('table', attrs={'id': 'rateListTable'}).find('tbody').find('tr').find('td', attrs={'class': 'rateDescription'}).find('p').contents[0].strip())
					except:
						name = None

		if name:
			e = StarwoodSetCode.create(set_code, name)
			self.response.out.write("Valid SET code.  Created entity.\n\n%s" % ({e.code: str(e.name)}))

		else:
			self.response.out.write("Invalid SET code.")



class SetCodeRateBlockLookupTask(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		queue_name = "setcoderate-lookup"

		offset = int(self.request.get('offset', default_value=0))
		limit = int(self.request.get('limit', default_value=1000))

		try:
			hotel_id = int(self.request.get('hotel_id', default_value=1234))
		except:
			hotel_id = 1234

		try:
			check_in = helper.str_to_date(self.request.get('check_in'))
		except:
			check_in = datetime.date.today() + relativedelta(months=1)

		nights = int(self.request.get('nights', default_value=1))
		check_out = check_in + relativedelta(days=nights)
		
		session_cookie = json.loads(self.request.get('session_cookie'))

		self.response.out.write('Creating SET lookup tasks using hotel #%d, from %s to %s...\n' \
									% (hotel_id, helper.date_to_str(check_in), \
									helper.date_to_str(check_out)))

		prefix_len = len('StarwoodSetCode_')
		for i, set_code in enumerate([int(key.name()[prefix_len:]) for key in db.Query(StarwoodSetCode, keys_only=True).filter('chainwide_rate =', False).filter('chainwide_discount =', False).order('code').fetch(limit=limit, offset=offset)]):
			task_name = "setcoderatelookup-%d-%d-%s-%s-%d" \
							% (set_code, hotel_id, \
								''.join(helper.date_to_str(check_in).split('-')), \
								''.join(helper.date_to_str(check_out).split('-')), \
								int(time.time()))

			task = taskqueue.Task(url='/tasks/%s' % queue_name, \
									name=task_name, method='GET', \
									params={'set_code': set_code, \
											'hotel_id': hotel_id, \
											'check_in': check_in, \
											'check_out': check_out, \
											'session_cookie': json.dumps(session_cookie)})

			d = (offset + i, task.name, queue_name)
			try:
				task.add(queue_name)
				self.response.out.write("%d.\tAdded task '%s' to task queue '%s'.\n" % d)
			except TaskAlreadyExistsError:
				self.response.out.write("%d.\tTask '%s' already exists in task queue '%s'.\n" % d)
			except TombstonedTaskError:
				self.response.out.write("%d.\tTask '%s' is tombstoned in task queue '%s'.\n" % d)





# http://localhost:8102/tasks/setcoderate-lookup?hotel_id=1234&set_code=8345&check_in=2010-11-10&check_out=2010-11-12
# http://www.awardpad.com/tasks/setcoderate-lookup?hotel_id=1234&set_code=8345&check_in=2010-11-10&check_out=2010-11-12
class SetCodeRateLookupTask(webapp.RequestHandler):
	def do_lookup(self):
		def clean_detail(soup):
			return str(' '.join(soup.contents[0].replace('\n', ' ').split()).strip())
		
		def parse_rate_details(rate_row):
			rate_details = {}
			bed_info = clean_detail(rate_row.find('td', attrs={'class': 'bedType'}).find('p'))
			rate_details['bed_count'], rate_details['bed_type'] = int(bed_info.split()[0]), ' '.join(bed_info.replace(' Beds', '').split()[1:])
			rate_details['description'] = clean_detail(rate_row.find('td', attrs={'class': 'roomFeatures'}).find('p'))
			
			rate_detail_id = int(re.match(r"^getRateDetail\('(\d+)', '(\w+)'\)$", rate_row.find('td', attrs={'class': 'rateDescription'}).find('a')['onclick']).group(1))
			
		
			rate_cell = rate_row.find('td', attrs={'class': 'averageDailyRatePerRoom'})
			rate_details['rate'] = {}
		
			try:
				currency, room_rate = clean_detail(rate_cell.find('p')).split()
			except:
				room_rate = None
		
			if room_rate:
				rate_details['rate']['room'] = float(room_rate)
				rate_details['rate']['currency'] = currency
			
				try:
					rate_details['rate']['total'] = float(clean_detail(rate_cell.find('p', 'roomTotal').find('a')).split()[1])
				except:
					pass
		
			return rate_details, rate_detail_id
		
		# https://www.starwoodhotels.com/preferredguest/search/ratedetail.html?ctx=ctxRooms&id=26370&ratePlanID=SETAND&workflow=35fdcd50-8400-4522-bbbd-bdf7773a6fa5&propertyID=1030
		def more_rate_details(hotel_id, rate_detail_id, workflow_id, session_cookie):
			#logging.info("session_cookie: %s" % session_cookie)
			url = "https://www.starwoodhotels.com/preferredguest/search/ratedetail.html?ctx=ctxRooms&id=%d&ratePlanID=%s&workflow=%s&propertyID=%d&searchCode=&sortOrder=&iATANumber=#undefined" \
 					% (rate_detail_id, 'SETAND', workflow_id, hotel_id)
			response = urlfetch.fetch(url, deadline=10, headers=session_cookie)
			soup = BeautifulSoup(response.content)
			rate_plan_desc = soup.prettify()
			'''
			rate_plan_desc = clean_detail(soup.find('div', text="Rate Plan Description").nextSibling.contents[0])
			'''
			#logging.info("\n\n\n\n%s\n\n\n\n" % rate_plan_desc)
	
		self.response.headers['Content-Type'] = 'text/plain'
		rate_data = {}

		try:
			set_code = int(self.request.get('set_code', 0))
		except:
			set_code = None

		try:
			hotel_id = int(self.request.get('hotel_id', 0))
		except:
			hotel_id = None

		name = None

		if not (set_code and hotel_id):
			rate_data['error'] = "Required set code and hotel id."
		
		else:
			try:
				check_in = helper.str_to_date(self.request.get('check_in'))
			except:
				check_in = datetime.date.today() + relativedelta(months=1)
			
			try:
				check_out = helper.str_to_date(self.request.get('check_out'))
			except:
				check_out = check_in + relativedelta(days=1)
			
			try:
				session_cookie = json.loads(self.request.get('session_cookie'))
			except:
				session_cookie = None
				
			if not session_cookie:
				session_cookie = helper_starwood.get_session_cookie()
		
			#url = "https://www.starwoodhotels.com/preferredguest/search/ratelist.html?corporateAccountNumber=%d&lengthOfStay=1&roomOccupancyTotal=001&requestedChainCode=SI&requestedAffiliationCode=SI&theBrand=SPG&submitActionID=search&arrivalDate=2010-09-15&departureDate=2010-09-16&propertyID=%d&ciDate=09/15/2010&coDate=09/19/2010&numberOfRooms=01&numberOfAdults=01&roomBedCode=&ratePlanName=&accountInputField=57464&foo=5232"
			url = "https://www.starwoodhotels.com/preferredguest/search/ratelist.html?arrivalDate=%s&departureDate=%s&corporateAccountNumber=%d&propertyID=%d" \
					% (helper.date_to_str(check_in), helper.date_to_str(check_out), set_code, hotel_id)
			try:
				response = urlfetch.fetch(url, deadline=10)
			except DownloadError, details:
				logging.error("DownloadError: %s" % details)
				response = None

			if response:
				soup = BeautifulSoup(response.content)
				try:
					rate_name = clean_detail(soup.find('table', attrs={'id': 'rateListTable'}).find('tbody').find('tr').find('td', attrs={'class': 'rateDescription'}).find('p'))
				except:
					rate_name = None
				
				try:
					workflow_id = soup.find('form', attrs={'name': 'RateListForm'}).find('input', attrs={'name': 'workflowId'})['value']
				except:
					workflow_id = None
					
				room_rates_data = []
				for lowest_rate in soup.findAll('p', attrs={'class': 'roomRate lowestRateIndicator'}):
					room_rate_data, rate_detail_id = parse_rate_details(lowest_rate.parent.parent)
					room_rates_data.append(room_rate_data)
					
				more_rate_details(hotel_id, rate_detail_id, workflow_id, session_cookie)
					
				rate_data = {'set_code': set_code, 'hotel_id': hotel_id, \
								'check_in': helper.date_to_str(check_in), \
								'check_out': helper.date_to_str(check_out), \
								'rate_name': rate_name, 'rooms': room_rates_data}
	
		return rate_data
	
	
	def get(self):
		hotel_id = int(self.request.get('hotel_id'))
		set_code = int(self.request.get('set_code'))
		check_in = helper.str_to_date(self.request.get('check_in'))
		check_out = helper.str_to_date(self.request.get('check_out'))
		
		url = "http://%s/sandbox/setcoderate?hotel_id=%d&set_code=%d&check_in=%s&check_out=%s" % \
				(self.request.headers.get('host'), hotel_id, set_code, helper.date_to_str(check_in), helper.date_to_str(check_out))
	
		rate_details = self.do_lookup() #json.loads(urlfetch.fetch(url, deadline=10).content)
		logging.info("%s\n\n" % json.dumps(rate_details))
		
		msg = "SetCodeRateLookupTask: %s\n" % json.dumps({'hotel_id': hotel_id, 'set_code': set_code})
		logging.info(msg)
		self.response.out.write(msg)
		
		for room in rate_details.get('rooms'):
			pk = (hotel_id, set_code, check_in, check_out, room['bed_count'], room['bed_type'])
			rate_lookup = StarwoodSetCodeRate.lookup(*pk)
			
			# new room is one that isn't in the DB yet
			new_room = False
			if not rate_lookup:
				new_room = True
				rate_lookup = StarwoodSetCodeRate.create(*pk)

			rate_lookup.description = room['description']
			rate_data = room['rate']
			rate_lookup.currency = rate_data.get('currency', 'USD')
			rate_lookup.room_rate = rate_data['room']
			rate_lookup.total_rate = rate_data.get('total')
		
			rate_lookup.put()
			
			room_msg = "\t%s room: %s\n" % (["OLD", "NEW"][new_room], json.dumps({'room_rate': rate_lookup.room_rate, 'bed_count': room['bed_count'], 'bed_type': room['bed_type']}))
			logging.info(room_msg)
			self.response.out.write(room_msg)
			


def main():
	ROUTES = [
		('/tasks/setcoderateblock-lookup', SetCodeRateBlockLookupTask),
		('/tasks/setcoderate-lookup', SetCodeRateLookupTask),
		('/tasks/setcode', SetCodeLookupTask),
		('/tasks/availability/process', ProcessStarwoodAvailability),
		('/tasks/availability/fetch', FetchStarwoodAvailability),
		('/tasks/hotel', StarwoodPropertyProcesser),
	]
	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)



if __name__ == "__main__":
	main()