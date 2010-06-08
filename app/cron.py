import os
import wsgiref.handlers

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import urlfetch
from google.appengine.api.labs import taskqueue
from google.appengine.api.labs.taskqueue import TaskAlreadyExistsError, TombstonedTaskError

from app.parsers import StarwoodParser
from app.models import StarwoodProperty, StarwoodPropertyCounter

import logging
logging.getLogger().setLevel(logging.DEBUG)

LIMIT = 200
TASK_QUEUE = "starwood-properties"

class FetchProperty(webapp.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		
		start_prop_id = int(self.request.get("prop_id", 0))
		if not start_prop_id:
			start_prop_id = StarwoodPropertyCounter.get_and_increment(LIMIT)
			
		if start_prop_id < 200000:
			task_name = "starwood-property-%d"
			for prop_id in xrange(start_prop_id, start_prop_id + LIMIT):
				task = taskqueue.Task(url='/tasks/property', params={'prop_id': prop_id}, \
										name=task_name % prop_id, method='GET')
				try:
					task.add(TASK_QUEUE)
					self.response.out.write("Added property id %s to task queue '%s'.\n" % (prop_id, TASK_QUEUE))
				except TaskAlreadyExistsError:
					self.response.out.write("Task '%s' already exists.\n" % (task.name))
				except TombstonedTaskError:
					self.response.out.write("Task '%s' is tombstoned.\n" % (task.name))
				
				#self.response.out.write("Could not add task '%s'.\n" % (task.name))
		

def main():
	ROUTES = [
		('/cron/property', FetchProperty)
	]

	application = webapp.WSGIApplication(ROUTES, debug=True)
	run_wsgi_app(application)

    
if __name__ == "__main__":
    main()