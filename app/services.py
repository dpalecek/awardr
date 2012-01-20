import logging
logging.getLogger().setLevel(logging.DEBUG)

from google.appengine.api import memcache
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

from app import helper
from app.parsers import StarwoodParser
from app.models import StarwoodProperty

import json


class AllHotels(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps( \
            {'hotels': [hotel.props() for hotel in StarwoodProperty.all()]}))


class HotelsLookup(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'

        try:
            sw = {'lat': float(self.request.get('w')), 'lng': float(self.request.get('s'))}
        except:
            sw = None
        try:
            ne = {'lat': float(self.request.get('e')), 'lng': float(self.request.get('n'))}
        except:
            ne = None

        logging.info("sw: %s, ne: %s" % (sw, ne))

        hotels = memcache.get('hotels')
        if not hotels or not len(hotels):
            hotels = [hotel for hotel in StarwoodProperty.all().filter('location !=', None)]
            memcache.set('hotels', hotels)

        if sw and ne:
            hotels = []  # [hotel for hotel in hotels if in_viewport(hotel.location, sw, ne)]

        self.response.out.write(json.dumps({'hotels': [hotel.props() for hotel in hotels]}))


AUTOCOMPLETE_LIMIT = 10


class HotelsAutocomplete(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        matched_hotels = []
        matched_count = 0

        query = self.request.get('term') or self.request.get('q')
        if query:
            query = query.strip().lower()
            for hotel in StarwoodProperty.all_cache().fetch(2000):
                if hotel.name.lower().find(query) != -1 \
                                or hotel.city.lower().find(query) != -1 \
                                or hotel.country.lower().find(query) != -1 \
                                or str(hotel.id) == query:
                    matched_hotels.append(hotel.props(props_filter=["name", "id", "category", "city", "country"]))
                    matched_count += 1
                    if matched_count >= AUTOCOMPLETE_LIMIT:
                        break

        self.response.out.write(json.dumps(matched_hotels))


class HotelsJS(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/javascript'

        def autocomplete_format(hotel_props):
            return {'value': hotel_props['id'], \
                    'label': "%s" % hotel_props['name'],
                    'desc': "%s, %s - Category %d" % (hotel_props['city'], hotel_props['country'], hotel_props['category'])}

        hotels = [autocomplete_format(hotel.props(props_filter=["name", "id", "category", "city", "country"])) for hotel in StarwoodProperty.all()]
        #hotels = [str(helper.remove_accents(hotel.name)) for hotel in StarwoodProperty.all()]
        template_values = {'hotels': json.dumps(hotels)}
        self.response.out.write(template.render(helper.get_template_path('hotels', extension='js'),
                                template_values))


class HotelAvailability(webapp.RequestHandler):
    def get(self, hotel_id):
        self.response.headers['Content-Type'] = 'application/json'

        try:
            hotel_id = int(hotel_id)
        except:
            hotel_id = 0

        self.response.out.write(json.dumps({ \
            'availability': StarwoodParser.parse_availability(hotel_id, \
                self.request.get('start_date'), self.request.get('end_date'), \
                self.request.get('ratecode')).get('availability')}))


def main():
    ROUTES = [
        ('/services/hotels.js', HotelsJS),
        ('/services/autocomplete/hotels.json', HotelsAutocomplete),
        ('/services/availability/(.*)/data.json', HotelAvailability),
        ('/services/hotels.json', HotelsLookup),
        ('/services/hotels_all.json', AllHotels),
    ]
    application = webapp.WSGIApplication(ROUTES, debug=True)
    run_wsgi_app(application)


if __name__ == "__main__":
    main()
