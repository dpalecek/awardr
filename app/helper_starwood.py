import logging
logging.getLogger().setLevel(logging.DEBUG)

from google.appengine.dist import use_library
try:
	use_library('django', '1.2')
except:
	logging.error("Couldn't load Django 1.2")
	
from google.appengine.api import urlfetch


def get_session_cookie():
	response = urlfetch.fetch('http://www.starwoodhotels.com/preferredguest/account/sign_in.html?login=%s&password=%s' % ('awardpad', 'Jordan23'))
	return {'Cookie': "JSESSIONID=%s" % response.headers.get('set-cookie').split('JSESSIONID=')[1].split(';')[0]}