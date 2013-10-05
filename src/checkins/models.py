from google.appengine.ext import ndb
from datetime import datetime,timedelta
from src.accounts.models import UserAccount
from src.guests.models import Guest

class CheckIn(ndb.Model):
	guest_key = ndb.KeyProperty(kind=Guest)
	restaurant_key = ndb.KeyProperty(kind=UserAccount)
	first_name = ndb.StringProperty(required=False)
	last_name = ndb.StringProperty(required=False)
	in_queue = ndb.BooleanProperty(required=True)
	signin_time = ndb.DateTimeProperty(auto_now_add=True)
	seat_time = ndb.DateTimeProperty(required=False)
	wait_time = ndb.FloatProperty(required=False)