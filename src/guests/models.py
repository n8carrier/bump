from google.appengine.ext import ndb
import logging
from src.accounts.models import UserAccount
from src.accounts import current_user
from flaskext import login as flasklogin

class Guest(ndb.Model):
	first_name = ndb.StringProperty(required=False)
	last_name = ndb.StringProperty(required=False)
	sms_number = ndb.StringProperty(required=False)
	email = ndb.StringProperty(required=False)
	preferred_contact = ndb.StringProperty(required=False)
	opt_in = ndb.BooleanProperty(required=True)
	restaurant_key = ndb.KeyProperty(kind=UserAccount)
	session_id = ndb.StringProperty(required=False) #For demo login only (so we can clear them)
		
	@classmethod
	def get_by_key(cls,guest_key=None):
		"""Convert an guest_key to an Guest object
		
		Arguments:
		guest_key -- the guest_key being searched
		
		Return value:
		An instance of a Guest object with the given guest_key; if the key could not be resolved
		to an Guest object, returns None
		
		"""
		if not guest_key:
			logging.error("Guest.get_by_key() called without a guest key")
			return None
		logging.debug("Guest.get_by_key(%s)" % guest_key)
		guest = Guest.query(Guest.guest_key==guest_key).get()
		return guest
	
	@classmethod
	def add_guest(self,firstName,lastName,smsNumber,email,preferredContact,optIn):
		cur_user = current_user()
		if cur_user.demo_mode():
			session_id = str(flasklogin.get_session_id())
		else:
			session_id = None
		# Check to see if guest is already in datastore
		if preferredContact == 'sms':
			if cur_user.demo_mode():
				guest = Guest.query(Guest.sms_number==smsNumber,Guest.restaurant_key==cur_user.key,Guest.session_id==session_id).get()
			else:
				guest = Guest.query(Guest.sms_number==smsNumber,Guest.restaurant_key==cur_user.key).get()
		elif preferredContact == 'email':
			if cur_user.demo_mode():
				guest = Guest.query(Guest.email==email,Guest.restaurant_key==cur_user.key,Guest.session_id==session_id).get()
			else:
				guest = Guest.query(Guest.email==email,Guest.restaurant_key==cur_user.key).get()
		else:
			guest = None
		if guest:
			# Guest is in datastore, update in case info has changed
			guest.first_name = firstName
			guest.last_name = lastName
			guest.preferred_contact = preferredContact
			if not optIn:
				# If they've opted in previously and they didn't check now, leave opted in
				guest.opt_in = optIn
		else:
			# Guest is not in datastore, create new Guest
			if cur_user.demo_mode():
				guest = Guest(first_name=firstName, last_name=lastName, sms_number = smsNumber, email=email, preferred_contact=preferredContact, opt_in=optIn, restaurant_key=cur_user.key, session_id=session_id)
			else:
				guest = Guest(first_name=firstName, last_name=lastName, sms_number = smsNumber, email=email, preferred_contact=preferredContact, opt_in=optIn, restaurant_key=cur_user.key)
			if cur_user.demo_mode():
				guest.session_id = str(flasklogin.get_session_id())
		guest.put()
		return guest