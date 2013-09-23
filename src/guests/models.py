from google.appengine.ext import ndb
from datetime import datetime,timedelta
import logging
from src.accounts.models import UserAccount
import urllib
from google.appengine.api import urlfetch
import json

class Guest(ndb.Model):
	first_name = ndb.StringProperty(required=False)
	last_name = ndb.StringProperty(required=False)
	sms_number = ndb.StringProperty(required=False)
	email = ndb.StringProperty(required=False)
	preferred_contact = ndb.StringProperty(required=True)
	opt_in = ndb.BooleanProperty(required=True)
	in_que = ndb.BooleanProperty(required=True)
	last_checkin = ndb.DateTimeProperty(auto_now_add=True)
	#restaurant_key = ndb.KeyProperty(required=True,kind=UserAccount)
	#item_key = ndb.StringProperty(required=True) #Unique, Key
	#item_type = ndb.StringProperty(required=True)
	#last_update = ndb.DateTimeProperty()
	#title = ndb.StringProperty(required=True)
	#author_director = ndb.StringProperty(required=True)
	#thumbnail_link = ndb.StringProperty(required=True)
		
	#@classmethod
	#def get_by_key(cls,guest_key=None):
	#	"""Convert an guest_key to an Guest object
	#	
	#	Arguments:
	#	guest_key -- the guest_key being searched
	#	
	#	Return value:
	#	An instance of a Guest object with the given guest_key; if the key could not be resolved
	#	to an Guest object, returns None
	#	
	#	"""
	#	if not guest_key:
	#		logging.error("Guest.get_by_key() called without a guest key")
	#		return None
	#	logging.debug("Guest.get_by_key(%s)" % guest_key)
	#	guest = Guest.query(Guest.guest_key==guest_key).get()
	#	return guest