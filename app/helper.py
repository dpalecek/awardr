import os
import unicodedata
from datetime import date, datetime

from google.appengine.api import users

import logging
logging.getLogger().setLevel(logging.DEBUG)


def init_template_values(user=None):    
	return {}

def get_template_path(template_name, extension=None):
	return os.path.join(os.path.dirname(__file__), "templates/%s.%s" \
							% (template_name, extension or "html"))

def remove_accents(str):
	return unicodedata.normalize('NFKD', unicode(str)).encode('ASCII', 'ignore')	
	
def str_to_date(s):
	return date(*(datetime.strptime("%s-01" % (s), "%Y-%m-%d").timetuple()[:3]))