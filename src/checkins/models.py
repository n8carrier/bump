from google.appengine.ext import ndb
from datetime import datetime
from src.accounts.models import UserAccount
from src.accounts import  current_user
from src.guests.models import Guest

class CheckIn(ndb.Model):
	guest_key = ndb.KeyProperty(kind=Guest)
	restaurant_key = ndb.KeyProperty(kind=UserAccount)
	first_name = ndb.StringProperty(required=False)
	last_name = ndb.StringProperty(required=False)
	party_size = ndb.IntegerProperty(default=2)
	in_queue = ndb.BooleanProperty(required=True)
	signin_time = ndb.DateTimeProperty(auto_now_add=True)
	wait_estimate = ndb.IntegerProperty(required=True)
	seat_time = ndb.DateTimeProperty(required=False)
	wait_time = ndb.FloatProperty(required=False)

	@classmethod
	def check_in_guest(self,guest,partySize=None,waitEstimate=None):
		cur_user = current_user()
		if not waitEstimate:
			# Wait estimate isn't defined (likely coming from guest sign-in), use default
			waitEstimate=cur_user.default_wait
		if waitEstimate == 0:
			# Currently no wait, don't put them in the queue
			inQueue = False
		else:
			inQueue = True
		# See if guest is already in queue, if so overwrite
		checkin = CheckIn.query(CheckIn.guest_key==guest.key, CheckIn.restaurant_key==cur_user.key, CheckIn.in_queue==inQueue).get()
		if checkin:
			# Guest is in queue already, update 
			checkin.last_name=guest.last_name
			checkin.first_name=guest.first_name
			checkin.signin_time=datetime.now()
			checkin.wait_estimate=waitEstimate
			if partySize:
				checkin.party_size=partySize
		else:
			# Guest is not in queue, create checkin
			if not partySize:
				partySize = 2
			checkin = CheckIn(guest_key=guest.key, restaurant_key=cur_user.key, first_name=guest.first_name, last_name=guest.last_name, in_queue=inQueue, party_size=partySize, signin_time=datetime.now(), wait_estimate=waitEstimate)
		checkin.put()
		return checkin