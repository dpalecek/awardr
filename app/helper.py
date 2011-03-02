import re, os, unicodedata, random
from datetime import date, datetime

import logging
logging.getLogger().setLevel(logging.DEBUG)

from google.appengine.dist import use_library
try:
	use_library('django', '1.2')
except:
	logging.error("Couldn't load Django 1.2")

from google.appengine.api import users, urlfetch

try: import json
except ImportError: import simplejson as json


def is_prod():
	return not os.environ['SERVER_SOFTWARE'].startswith('Dev')

def init_template_values(init_dict={}, user=None, uses_google_maps=False):
	t = {'uses_google_maps': uses_google_maps}
	t.update(init_dict)
	return t

def get_template_path(template_name, extension=None):
	return os.path.join(os.path.dirname(__file__), "templates/%s.%s" \
							% (template_name, extension or "html"))

def remove_accents(str):
	return unicodedata.normalize('NFKD', unicode(str)).encode('ASCII', 'ignore')	
	
def str_to_date(s):
	date_format = ("%s-01", "%s")[len(s.split('-')) == 3]
	return date(*(datetime.strptime(date_format % s, "%Y-%m-%d").timetuple()[:3]))
	
def date_to_str(d):
	return d.strftime("%Y-%m-%d")

def slugify(text, separator="-"):
	ret = ""
	
	text = remove_accents(text)
	for c in text.lower():
		try:
			ret += htmlentitydefs.codepoint2name[ord(c)]
		except:
			ret += c

	ret = re.sub("([a-zA-Z])(uml|acute|grave|circ|tilde|cedil)", r"\1", ret)
	ret = re.sub("\W", " ", ret)
	ret = re.sub(" +", separator, ret)

	return ret.strip()

def currency_conversion(currency, amount):
	def currency_conversion_xurrency(currency, amount):
		response = urlfetch.fetch("http://xurrency.com/api/%s/usd/%.2f" \
									% (currency.lower(), amount))
		return float(json.loads(response.content)['result']['value'])

	def currency_conversion_exchangerate(currency, amount):
		url = "http://www.exchangerate-api.com/%s/usd/%.2f?k=%s" \
				% (currency.lower(), amount, \
					random.choice(["t6WyG-bRPzN-wcxGF", "xvtMg-KjqAV-x7dmO"]))
		response = urlfetch.fetch(url)
		return float(response.content)
	
	for converter in [currency_conversion_exchangerate, currency_conversion_xurrency]:
		try:
			return converter(currency, amount)
		except:
			pass
	
	return None