import math

from google.appengine.ext import db
from google.appengine.api import memcache

from app.models import StarwoodProperty


def great_circle_distance(coord1, coord2):
	d_lng = coord2['lng'] - coord1['lng']
	d_lat = coord2['lat'] - coord1['lat']
	a = (math.sin(d_lat / 2))**2 + math.cos(coord1['lat']) * math.cos(coord2['lat']) * (math.sin(d_lng / 2))**2
	c = 2 * math.asin(min(1, math.sqrt(a)))
	dist = 3956 * c
	return dist


class HotelManager():
	@staticmethod
	def nearest(coord, limit=20):
		hotel_distance_map = {}
		for hotel in [hotel for hotel in StarwoodProperty.all() if hotel.location]:
			hotel_distance_map[great_circle_distance(coord, \
				{'lat': hotel.location.lat, 'lng': hotel.location.long})] = hotel
		
		if limit == -1:
			hotel_keys = sorted(hotel_distance_map.keys())
		else:
			hotel_keys = sorted(hotel_distance_map.keys())[:limit]
			
		hotels = []
		for hotel_key in hotel_keys:
			hotels.append(hotel_distance_map[hotel_key])
		
		return hotels