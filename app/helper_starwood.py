import logging
logging.getLogger().setLevel(logging.DEBUG)

from google.appengine.api import urlfetch


def get_session_cookie():
    response = urlfetch.fetch('http://www.starwoodhotels.com/preferredguest/account/sign_in.html?login=%s&password=%s' % ('awardpad', 'Jordan23'))
    return {'Cookie': "JSESSIONID=%s" % response.headers.get('set-cookie').split('JSESSIONID=')[1].split(';')[0]}
