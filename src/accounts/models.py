from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api.datastore import Key
from datetime import datetime,timedelta
from flaskext.login import AnonymousUser
from werkzeug.security import generate_password_hash, check_password_hash
import logging

class UserAccount(ndb.Model):
	"""Stored information about a User"""
	
	name = ndb.StringProperty(required=True)
	email = ndb.StringProperty(required=True)
	default_msg_ready = ndb.StringProperty(default="{firstName}, your table is almost ready. Need more time? Reply ""bump"" and the # of minutes you'd like.")
	default_checkbox_promos = ndb.BooleanProperty(default=False)
	is_admin = ndb.BooleanProperty(default=False)
	gv_email  = ndb.StringProperty(required=False)
	gv_password = ndb.StringProperty(required=False)
	reply_to_email  = ndb.StringProperty(required=False)
	default_wait = ndb.IntegerProperty(default=15)
	
	def demo_mode(self):
		if self.email == 'demo@bumpapp.co':
			return True
		else:
			return False
	
	def update(self,defaultMessage, promoDefault, gv_email, gv_password, reply_to_email, default_wait):
		
		# validate name
		self.default_msg_ready = defaultMessage
		self.default_checkbox_promos = promoDefault
		if gv_password:
			self.gv_email = gv_email
			self.gv_password = gv_password
		self.reply_to_email = reply_to_email
		if default_wait:
			self.default_wait = default_wait
		self.put()
		return True

	def is_authenticated(self):
		"""determine whether the UserAccount is authenticated
		
		This method is required by the flask-login library
		
		Return value:
		True (note: the AnonymousUser object returns False for this method)
		
		"""
		return True

	def is_active(self):
		"""determine whether the UserAccount is active or not
		
		This method is required by the flask-login library
		
		Return value:
		True if the account is active; False otherwise
		
		"""
		return True

	def is_anonymous(self):
		"""determine whether the UserAccount is anonymous
		
		This method is required by the flask-login library
		
		Return value:
		False (note: the AnonymousUser object returns True for this method)
		
		"""
		return False

	def get_id(self):
		"""get the id for this UserAccount
		
		This method is required by the flask-login library
		
		Return value:
		Integer that represents the unique ID of this UserAccount
		
		"""
		return self.key.id()

	@classmethod
	def create_user(cls,g_user,make_admin=False):
		if UserAccount.get_by_email(g_user.email()):
			return None
		user = UserAccount(name=g_user.nickname(),email=g_user.email(),is_admin=make_admin)
		if user:
			user.put()
			return user
		else:
			return None

	@classmethod
	def can_delete_user(cls,user):
		return True

	@classmethod
	def delete_user(cls,user):
		"""Deletes the given user from the system
		Also deletes the connection with each user it is connected to

		Arguments:
		user - The UserAccount object that should be deleted
		"""
		if UserAccount.can_delete_user(user):
			user.key.delete()
			return True
		return None

	@classmethod
	def getuser(cls,userid):
		return UserAccount.get_by_id(userid)
	
	@classmethod
	def get_by_email(cls,email):
		user = cls.query(cls.email==email).get()
		return user
	
	def get_guests(self):
		from src.guests.models import Guest
		return Guest.query(Guest.restaurant_key==self.key).fetch()
	
	def get_checkedin_guests(self):
		from src.guests.models import Guest
		from src.checkins.models import CheckIn
		return CheckIn.query(CheckIn.restaurant_key==self.key,CheckIn.in_queue==True).fetch()
	
class Anonymous(AnonymousUser):
	name = u"Anonymous"
