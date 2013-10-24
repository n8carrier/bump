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
	subscribe_date = ndb.DateTimeProperty(auto_now_add=True) # Date guest object was created, technically should be date opted in, but not critical
	signup_method = ndb.IntegerProperty(required=False) # 1 = Waitlist Opt-In; 2 = SMS (text to number); 3 = Website
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
	def add_guest(self,firstName,lastName,smsNumber,email,preferredContact,optIn,signup_method,user=None):
		if not user:
			user = current_user()
		if user.demo_mode():
			session_id = str(flasklogin.get_session_id())
		else:
			session_id = None
		# Check to see if guest is already in datastore
		if not smsNumber and not email:
			# If both are blank there's no way to know the name matches any other instance of the name, so create a new guest.
			guest = None
		elif preferredContact == 'sms':
			if user.demo_mode():
				guest = Guest.query(Guest.sms_number==smsNumber,Guest.restaurant_key==user.key,Guest.session_id==session_id).get()
			else:
				guest = Guest.query(Guest.sms_number==smsNumber,Guest.restaurant_key==user.key).get()
		elif preferredContact == 'email':
			if user.demo_mode():
				guest = Guest.query(Guest.email==email,Guest.restaurant_key==user.key,Guest.session_id==session_id).get()
			else:
				guest = Guest.query(Guest.email==email,Guest.restaurant_key==user.key).get()
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
			if user.demo_mode():
				guest = Guest(first_name=firstName, last_name=lastName, sms_number = smsNumber, email=email, preferred_contact=preferredContact, opt_in=optIn, signup_method=signup_method, restaurant_key=user.key, session_id=session_id)
			else:
				guest = Guest(first_name=firstName, last_name=lastName, sms_number = smsNumber, email=email, preferred_contact=preferredContact, opt_in=optIn, signup_method=signup_method, restaurant_key=user.key)
			if user.demo_mode():
				guest.session_id = str(flasklogin.get_session_id())
		guest.put()
		return guest