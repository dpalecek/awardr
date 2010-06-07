from __future__ import division

import os

from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.ext import db

from xml.dom.minidom import parse, parseString
from google.appengine.api import urlfetch

import math
from datetime import date, datetime

import logging
logging.getLogger().setLevel(logging.DEBUG)



def init_template_values(user=None):
	template_values = {}      
	return template_values


def get_template_path(template_name, extension=None):
	if not extension:
		extension = "html"

	return os.path.join(os.path.dirname(__file__), "templates/%s.%s" % (template_name, extension))