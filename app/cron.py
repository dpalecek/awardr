import datetime
import time
import random
from collections import defaultdict

import logging
logging.getLogger().setLevel(logging.DEBUG)

from google.appengine.api import urlfetch, mail, taskqueue
from google.appengine.api.taskqueue import TaskAlreadyExistsError, TombstonedTaskError
from google.appengine.ext import db, webapp
from google.appengine.ext.webapp.util import run_wsgi_app

from app.models import StarwoodProperty, StarwoodDateAvailability, StarwoodSetCodeCounter, StarwoodSetCode
import app.helper as helper
import app.helper_starwood as helper_starwood

from lib.BeautifulSoup import BeautifulSoup
from lib.dateutil.relativedelta import relativedelta

import json


TASK_QUEUE_PROCESS_HOTEL = "starwood-properties"
TASK_NAME_PROCESS_HOTEL = "starwood-hotel-%d-%d"

TASK_QUEUE_FETCH_AVAILABILITY = "fetch-starwood-availability"
TASK_NAME_FETCH_AVAILABILITY = "fetch-starwood-availability-%d-%s-%04d%02d-%02d-%d"  # hotel_id, ratecode, start_date, delta
DATE_FORMAT = "%04d-%02d"
MONTHS_DELTA = 18


class LocationlessHotels(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        email_address = "mshafrir@gmail.com"

        hotels = StarwoodProperty.all().filter('location =', None)

        if hotels.count():
            body = "Hotels without a location.\n"
            for hotel in hotels:
                body = "%s\n%s" % (body, hotel)

            body = "%s\n\n%s" % (body, "https://appengine.google.com/datastore/explorer?submitted=1&app_id=awardr&viewby=gql&kind=StarwoodProperty&query=SELECT+*+FROM+StarwoodProperty+WHERE+location+%3D+NULL")

            self.response.out.write(body)
            mail.send_mail(email_address, email_address, \
                            "Awardpad: Hotels without a location.", body)

        else:
            self.response.out.write("All hotels with a location.")


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
        is_valid_property = lambda info_div: info_div.find('a', 'propertyName') is not None

        self.response.headers['Content-Type'] = 'text/plain'

        directory_hotels = {}

        directory_url = "https://www.starwoodhotels.com/corporate/directory/hotels/all/list.html?categoryFilter=%s" % int(category_id)
        directory_response = urlfetch.fetch(url=directory_url, deadline=10)

        if directory_response and directory_response.status_code == 200:
            soup = BeautifulSoup(directory_response.content)
            for link in [info_div.find('a', 'propertyName') for info_div in soup.findAll('div', 'propertyInfo') if is_valid_property(info_div)]:
                hotel_url = link.get('href')
                # id => brand
                directory_hotels[int(hotel_url.split('propertyID=')[1])] = str(hotel_url.split('/')[1])

        diff_ids = sorted(list(frozenset(directory_hotels.keys()) - frozenset([hotel.id for hotel in StarwoodProperty.all()])))

        added_task_count = 0

        if diff_ids:
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
        self.response.headers['Content-Type'] = 'text/plain'

        # months_delta = int(self.request.get('months', 1))

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
            logging.info("Getting availability for %s.\n" % hotel)

            self.response.out.write("Got hotel %s [%s].\n" % (hotel.name, hotel.id))
            added_task_count = 0

            ratecodes = ['SPG%d' % (hotel.category)]
            if hotel.category < 7:
                ratecodes.append('SPGCP')

            for ratecode in ratecodes:
                start_date = datetime.date.today()
                end_date = start_date + relativedelta(months=MONTHS_DELTA)

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

            hotel.last_checked = datetime.datetime.now()
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

        queue_name = "refresh-hotel"

        hotels = StarwoodProperty.all().fetch(10000)
        limit = 100
        hour = int(self.request.get('hour', datetime.datetime.now().hour))

        offset = min(hour, len(hotels) / limit)
        try:
            hotel_ids = [int(self.request.get('hotel_id'))]
        except:
            hotel_ids = xrange(offset * limit, (offset + 1) * limit)

        for hotel_id in hotel_ids:
            task_name = "hotel-refresh-%d-%d" % (hotel_id, int(time.time()))
            task = taskqueue.Task(url='/tasks/refresh-hotel', \
                                    name=task_name, method='GET', \
                                    params={'hotel_id': hotel_id})

            try:
                task.add(queue_name)
                self.response.out.write("Added task '%s' to task queue '%s'.\n" \
                                        % (task.name, queue_name))
            except TaskAlreadyExistsError:
                self.response.out.write("Task '%s' already exists in task queue '%s'.\n" \
                                        % (task.name, queue_name))
            except TombstonedTaskError:
                self.response.out.write("Task '%s' is tombstoned in task queue '%s'.\n" \
                                        % (task.name, queue_name))


class RemoveDuplicateAvailabilities(webapp.RequestHandler):
    def get(self):
        is_cron = bool(self.request.get('X-AppEngine-Cron', False))
        writer = (self.response.out.write, logging.info)[is_cron]

        self.response.headers['Content-Type'] = 'text/plain'
        writer("Clean out the availability dupes!\n\n")

        avails_to_del = []
        avail_map = defaultdict(list)

        try:
            limit = int(self.request.get('limit', 100))
        except:
            limit = 100

        dupes = 0
        for avail in StarwoodDateAvailability.all().order('date'):
            key = (avail.hotel.id, avail.ratecode, avail.date)
            avail_map[key].append(avail)

            if len(avail_map[key]) == 2:
                dupes += 2
            if len(avail_map[key]) > 2:
                dupes += 1

            if dupes >= limit:
                break

        nights_compare = lambda avail1, avail2: len(avail1.nights) - len(avail2.nights)

        for key, avails in ((key, avails) for key, avails in avail_map.iteritems() if len(avails) > 1):
            avails.sort(cmp=nights_compare)
            if not is_cron:
                writer("%s: Keeping %s, deleting %s and %d others.\n" % (key, avails[0].nights, avails[1].nights, len(avails) - 2))
            avails_to_del.extend(avails[1:])

        if is_cron or bool(self.request.get('persist', False)):
            writer("\nDeleting %d entities." % max(len(avails_to_del), 500))
            db.delete(avails_to_del[:500])


class CronSetCodeLookup(webapp.RequestHandler):
    def get(self):
        queue_name = "setcode-lookup"

        try:
            increment = int(self.request.get('increment', default_value=100))
        except:
            increment = 100

        try:
            hotel_id = int(self.request.get('hotel_id', default_value=1234))
        except:
            hotel_id = 1234

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('Creating SET lookup tasks...\n')

        counter = StarwoodSetCodeCounter.lookup()
        if not counter:
            counter = StarwoodSetCodeCounter.create()

        for code in xrange(counter.code, counter.code + increment):
            task_name = "setcode-%d-%d" % (code, int(time.time()))
            task = taskqueue.Task(url='/tasks/setcode', \
                                    name=task_name, method='GET', \
                                    params={'set_code': code, 'hotel_id': hotel_id})

            try:
                task.add(queue_name)
                self.response.out.write("Added task '%s' to task queue '%s'.\n" \
                                        % (task.name, queue_name))
            except TaskAlreadyExistsError:
                self.response.out.write("Task '%s' already exists in task queue '%s'.\n" \
                                        % (task.name, queue_name))
            except TombstonedTaskError:
                self.response.out.write("Task '%s' is tombstoned in task queue '%s'.\n" \
                                        % (task.name, queue_name))

        StarwoodSetCodeCounter.increment(increment)


class CronSetCodeRateLookupStarter(webapp.RequestHandler):
    """
    Cron job that kicks off a SET Code Rate lookup.
    """

    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        queue_name = "setcoderateblock-lookup"

        limit = int(self.request.get('limit', default_value=100))
        hotel_id = int(self.request.get('hotel_id', default_value=1234))
        try:
            check_in = helper.str_to_date(self.request.get('check_in'))
        except:
            check_in = datetime.date.today() + relativedelta(months=1)
        nights = int(self.request.get('nights', default_value=1))
        check_out = check_in + relativedelta(days=nights)

        session_cookie = helper_starwood.get_session_cookie()

        setcode_count = len(db.Query(StarwoodSetCode, keys_only=True).filter('chainwide_rate =', False).filter('chainwide_discount =', False).fetch(10000))
        self.response.out.write("StarwoodSetCode count: %d\n\n" % setcode_count)

        if True:
            for i, offset in enumerate(xrange(0, setcode_count, limit)):
                task_name = "setcoderate-block-%d-%s-%s-%d-%d-%d" \
                                % (hotel_id, \
                                    ''.join(helper.date_to_str(check_in).split('-')), \
                                    ''.join(helper.date_to_str(check_out).split('-')), \
                                    offset, offset + limit, int(time.time()))

                task = taskqueue.Task(url='/tasks/%s' % queue_name, \
                                        name=task_name, method='GET', \
                                        params={'hotel_id': hotel_id, \
                                                'check_in': check_in, \
                                                'check_out': check_out, \
                                                'offset': offset, \
                                                'limit': limit, \
                                                'session_cookie': json.dumps(session_cookie)})

                d = (i + 1, task.name, queue_name)
                try:
                    task.add(queue_name)
                    self.response.out.write("%d.\tAdded task '%s' to task queue '%s'.\n" % d)
                except TaskAlreadyExistsError:
                    self.response.out.write("%d.\tTask '%s' already exists in task queue '%s'.\n" % d)
                except TombstonedTaskError:
                    self.response.out.write("%d.\tTask '%s' is tombstoned in task queue '%s'.\n" % d)


def main():
    ROUTES = [
        ('/cron/setcoderate-starter', CronSetCodeRateLookupStarter),
        ('/cron/setcode-lookup', CronSetCodeLookup),
        ('/cron/remove-duplicate-availabilities', RemoveDuplicateAvailabilities),
        ('/cron/locationless', LocationlessHotels),
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
