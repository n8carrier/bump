from google.appengine.ext import ndb
from datetime import datetime
from src.accounts.models import UserAccount
from src.accounts import  current_user
from src.guests.models import Guest
from googlevoice.voice import Voice
from google.appengine.api import mail

class MessageTemplate(ndb.Model):
	restaurant_key = ndb.KeyProperty(kind=UserAccount)
	message_type = ndb.IntegerProperty(required=True) # 1 = Default Table Notification; 2 = Promo Message or Coupon
	is_active = ndb.BooleanProperty(required=True) # Rather than overwriting a message template, the old template should be deactivated and replaced. This allows preserving history without saving the message text for every message
	message_name = ndb.StringProperty(required=False) # Name of message, used for coupons/promos
	message_text = ndb.StringProperty(required=True)
	
	def update(self,message_text):
		cur_user = current_user()
	
		if self.message_text != message_text:
			# User has update message text, archive old and create new
			self.is_active = False
			self.put()
			msgTemplate = MessageTemplate(restaurant_key=cur_user.key,message_type=int(self.message_type),is_active=True,message_text=message_text)
			msgTemplate.put()
		
		return True
	
class Message(ndb.Model):
	restaurant_key = ndb.KeyProperty(kind=UserAccount) # Sender
	recipient_key = ndb.KeyProperty(kind=Guest) # Receiver
	message_template_key = ndb.KeyProperty(kind=MessageTemplate,required=False) # Reference to Message Template (includes message text); Not required, because custom messages won't reference a template
	contact_method = ndb.StringProperty(required=True) # 'sms' or 'email'
	time_initiated = ndb.DateTimeProperty(required=True)
	send_success = ndb.BooleanProperty(required=True) # True = Sent successfully; False = Unable to send
	
	@classmethod
	def send_notification(cls,guest_ID,msg_text=False):
		cur_user = current_user()
		guest = Guest.get_by_id(int(guest_ID))
		
		# Create Message Object
		msg = Message(restaurant_key = cur_user.key, recipient_key = guest.key, contact_method = guest.preferred_contact, time_initiated = datetime.now())
		
		# If a default notification, populate msg_text and store MessageTemplate Key
		if not msg_text:
			msgTemplate = MessageTemplate.query(MessageTemplate.restaurant_key==cur_user.key,MessageTemplate.message_type==1,MessageTemplate.is_active==True).get()
			if not msgTemplate:
				# No template exists (new user), create one
				msgTemplate = MessageTemplate(restaurant_key=cur_user.key,message_type=1,is_active=True,message_text="{firstName}, your table is almost ready. Need more time? Reply ""bump"" and the # of minutes you'd like.")
				msgTemplate.put()
			msg.message_template_key = msgTemplate.key
			msg_text = msgTemplate.message_text
			if guest.first_name:
				msg_text = msg_text.replace('{firstName}',guest.first_name)
			if guest.last_name:
				msg_text = msg_text.replace('{lastName}',guest.last_name)
		
		# Send Message
		if msg.send_message(guest,msg_text):
			msg.send_success = True
		else:
			msg.send_success = False
		
		# Store Message
		msg.put()
		
		# Return success
		return msg.send_success
	
	@classmethod
	def send_promo(cls,guest_ID,msgTemplate):
		cur_user = current_user()
		guest = Guest.get_by_id(int(guest_ID))
		
		# Create Message Object
		msg = Message(restaurant_key = cur_user.key, recipient_key = guest.key, contact_method = guest.preferred_contact, time_initiated = datetime.now(), message_template_key=msgTemplate.key)
		
		# Create msg_text from msgTemplate.message_text
		msg_text = msgTemplate.message_text
		if guest.first_name:
			msg_text = msg_text.replace('{firstName}',guest.first_name)
		if guest.last_name:
			msg_text = msg_text.replace('{lastName}',guest.last_name)
		
		# Send Message
		if msg.send_message(guest,msg_text):
			msg.send_success = True
		else:
			msg.send_success = False
		
		# Store Message
		msg.put()
		
		# Return success
		return msg.send_success
		
	def send_message(self,guest,msg_text):
		cur_user = current_user()
		if cur_user.demo_mode():
			msg = msg_text + " -- SENT BY BUMP DEMO: http://bumpapp.co"
		else:
			msg = msg_text
		if self.contact_method == 'sms':
			if cur_user.gv_email and cur_user.gv_password:
				gv_email = cur_user.gv_email
			else:
				gv_email = 'nate@consultboost.com'
			if cur_user.gv_email and cur_user.gv_password:
				gv_password = cur_user.gv_password
			else:
				gv_password = 'BumpGVB0t'
			voice = Voice()
			voice.login(gv_email,gv_password)
			phoneNumber = guest.sms_number
			text = msg
			voice.send_sms(phoneNumber, text)
		elif self.contact_method == 'email':
			if cur_user.reply_to_email:
				# User provided a reply-to email different from their account email. Emails must be sent out by the account, so a reply-to email is used.
				reply_to = cur_user.reply_to_email
				sender_email = cur_user.email
			else:
				if cur_user.demo_mode():
					# Demo mode is not a real account, so it must be sent from admin@bumpapp.co
					reply_to = "demo@bumpapp.co"
					sender_email = "admin@bumpapp.co"
				else:
					sender_email = cur_user.email
					reply_to = cur_user.email
			mail.send_mail(
				sender=cur_user.name + " <" + sender_email + ">",
				reply_to=reply_to,
				to=guest.email,
				subject="Table Notification",
				body=msg_text)
	
		
	
	#def check_in_guest(self,guest,partySize=None,waitEstimate=None):
	#	cur_user = current_user()
	#	if not waitEstimate:
	#		# Wait estimate isn't defined (likely coming from guest sign-in), use default
	#		waitEstimate=cur_user.default_wait
	#	if waitEstimate == 0:
	#		# Currently no wait, don't put them in the queue
	#		inQueue = False
	#	else:
	#		inQueue = True
	#	# See if guest is already in queue, if so overwrite
	#	checkin = CheckIn.query(CheckIn.guest_key==guest.key, CheckIn.restaurant_key==cur_user.key, CheckIn.in_queue==inQueue).get()
	#	if checkin:
	#		# Guest is in queue already, update 
	#		checkin.last_name=guest.last_name
	#		checkin.first_name=guest.first_name
	#		checkin.signin_time=datetime.now()
	#		checkin.wait_estimate=waitEstimate
	#		if partySize:
	#			checkin.party_size=partySize
	#	else:
	#		# Guest is not in queue, create checkin
	#		if not partySize:
	#			partySize = 2
	#		checkin = CheckIn(guest_key=guest.key, restaurant_key=cur_user.key, first_name=guest.first_name, last_name=guest.last_name, in_queue=inQueue, party_size=partySize, signin_time=datetime.now(), wait_estimate=waitEstimate)
	#	checkin.put()
	#	return checkin