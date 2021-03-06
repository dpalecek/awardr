import logging
logging.getLogger().setLevel(logging.DEBUG)

from google.appengine.ext import webapp

register = webapp.template.create_template_register()


@register.filter
def has_availability(hotel, available_hotel_ids):
    return hotel.id in available_hotel_ids

has_availability.is_safe = True
