from google.appengine.ext import ndb
#from src.messages.models import MessageTemplate
from flaskext.login import AnonymousUser

class UserAccount(ndb.Model):
	"""Stored information about a User"""
	
	name = ndb.StringProperty(required=True)
	email = ndb.StringProperty(required=True)
	#default_msg_ready = ndb.StringProperty(default="") # Deprecated 10/18/13, replaced by MessageTemplate
	default_checkbox_promos = ndb.BooleanProperty(default=True)
	is_admin = ndb.BooleanProperty(default=False)
	gv_email  = ndb.StringProperty(required=False)
	gv_password = ndb.StringProperty(required=False)
	reply_to_email  = ndb.StringProperty(required=False)
	default_wait = ndb.IntegerProperty(default=15)
	is_demo = ndb.BooleanProperty(default=False)
	
	def demo_mode(self):
		return self.is_demo
	
	def update(self, promoDefault, gv_email, gv_password, reply_to_email):
		
		# validate name
		#self.default_msg_ready = defaultMessage # Deprecated 10/18/13
		self.default_checkbox_promos = promoDefault
		if gv_password:
			self.gv_email = gv_email
			self.gv_password = gv_password
		self.reply_to_email = reply_to_email
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
		from src.checkins.models import CheckIn
		return CheckIn.query(CheckIn.restaurant_key==self.key,CheckIn.in_queue==True).fetch()
	
	def get_optins(self):
		from src.guests.models import Guest
		return Guest.query(Guest.restaurant_key==self.key,Guest.opt_in==True).fetch()
	
class Anonymous(AnonymousUser):
	name = u"Anonymous"
