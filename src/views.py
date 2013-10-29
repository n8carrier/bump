# Views
from google.appengine.api import users
from flask import Response, jsonify, render_template, request, url_for, redirect, flash, json
from flaskext.login import login_required, login_user, logout_user
from flaskext import login as flasklogin
from googlevoice.voice import Voice
from googlevoice.util import input
from src.guests.models import Guest
from src.checkins.models import CheckIn
from src.whitelist.models import Whitelist
from src.messages.models import MessageTemplate, Message
from src import functions
import logging
from decorators import crossdomain
from src import app
from utilities.JsonIterable import *
from accounts import login as login_account, logout as logout_account, join as join_account, delete as delete_account, current_user, login_required
from accounts.models import UserAccount
from google.appengine.api import mail
from google.appengine.ext import db
from datetime import date,timedelta
import time
import re

import filters


#mail = Mail(app)

def warmup():
	# https://developers.google.com/appengine/docs/python/config/appconfig#Warmup_Requests
	# This function loads the views into the new instance when
	# one has to start up due to load increases on the app
	return ''

#return (datetime.now() - self.last_update) > timedelta(minutes=1000)

@app.route("/crossdomain")
@crossdomain(origin='*')
def test_view():
	"""test view for checking accessibility of cross-domain ajax requests
	
	"""
	return "this is a response"

def render_response(template, *args, **kwargs):
	"""helper function for adding variables for the template processor
	
	"""
	return render_template(template, *args, user=current_user(), **kwargs)

################################ Website landing pages ##################################
def index():
	whitelist = request.args.get('whitelist')
	
	if request.method == 'POST':
		restaurantName = request.form["restaurantName"]
		fullName = request.form["fullName"]
		phoneNumber = request.form["phoneNumber"]
		emailAddress =  request.form["emailAddress"]
		msg = "The following individual has expressed interest in Bump:\r\n\r\nRestaurant: " + restaurantName + "\r\nName: " + fullName + "\r\nPhone Number: " + phoneNumber + "\r\nEmail Adress: " + emailAddress
		mail.send_mail(sender="nate@bumpapp.co",
			to="nate@bumpapp.co",
			subject="Interest in Bump",
			body=msg)
	
	return render_response('home.html',whitelist=whitelist)

def waitlist_manager():
	whitelist = request.args.get('whitelist')
	
	if request.method == 'POST':
		restaurantName = request.form["restaurantName"]
		fullName = request.form["fullName"]
		phoneNumber = request.form["phoneNumber"]
		emailAddress =  request.form["emailAddress"]
		msg = "The following individual has expressed interest in Bump:\r\n\r\nRestaurant: " + restaurantName + "\r\nName: " + fullName + "\r\nPhone Number: " + phoneNumber + "\r\nEmail Adress: " + emailAddress
		mail.send_mail(sender="nate@bumpapp.co",
			to="nate@bumpapp.co",
			subject="Interest in Bump",
			body=msg)
	
	return render_response('waitlist-manager.html',whitelist=whitelist)
		
def settings():
	cur_user = current_user()
	
	# Get message template
	msgTemplate = MessageTemplate.query(MessageTemplate.restaurant_key==cur_user.key,MessageTemplate.message_type==1,MessageTemplate.is_active==True).get()
	if not msgTemplate:
		# No template exists, create one
		msgTemplate = MessageTemplate(restaurant_key=cur_user.key,message_type=1,is_active=True,message_text="{firstName}, your table is almost ready. Need more time? Reply ""bump"" and the # of minutes you'd like.")
		msgTemplate.put()
	if cur_user.is_demo:
		# Don't let demo into settings
		return redirect(url_for("index"))
	else:
		if request.method == 'POST' and "defaultMessage" in request.form and "promoDefault" in request.form:
			defaultMessage = request.form["defaultMessage"]
			if request.form["promoDefault"].lower() == "true":
				promoDefault = True
			elif request.form["promoDefault"].lower() == "false":
				promoDefault = False
			if request.form["gvPW"]:
				gv_email = request.form["gvEmail"]
				gv_password = request.form["gvPW"]
			else:
				gv_email = None
				gv_password = None
			reply_to_email = request.form["replyEmail"]
			
			# Udpate Message Template
			if msgTemplate.update(defaultMessage) and cur_user.update(promoDefault, gv_email, gv_password, reply_to_email):
				return "Success"
			else:
				return False
		return render_response('settings.html',default_message=msgTemplate.message_text)
		
def guest_signin():
	cur_user = current_user()
	tour = request.args.get('tour')
	if cur_user:
		if request.method == 'POST':
			firstName = request.form["firstName"]
			try:
				lastName = request.form["lastName"]
			except:
				lastName = None
			preferredContact = request.form["preferredContact"]
			if preferredContact == 'sms':
				smsNumber = functions.digitizePhoneNumber(request.form["smsNumber"])
				email = None
			elif preferredContact == 'email':
				email = request.form["email"]
				smsNumber = None
			try:
				if request.form["optIn"] == 'on':
					optIn = True
				else:
					optIn = False
			except:
				optIn = False
			# Add guest to database
			guest = Guest.add_guest(firstName=firstName,lastName=lastName,preferredContact=preferredContact,smsNumber=smsNumber,email=email,optIn=optIn,signup_method=1,user=cur_user)
			if not guest:
				return "Error"
			checkin = CheckIn.check_in_guest(guest)
			if not checkin:
				return "Error"
			if tour == "continue":
				return redirect(url_for("manage") + '?tour=continue')
			return "Success"
	return render_response("guest-signin.html", tour=tour)

def whitelist():
	cur_user = current_user()
	if cur_user:
		if cur_user.is_admin:
			if request.method == 'POST':
				domain = request.form["domain"].lower()
				whitelistDomain = Whitelist.query(Whitelist.domain==domain).get()			
				if not whitelistDomain:
					whitelistDomain = Whitelist(domain=domain)
					whitelistDomain.put()
			return render_response("whitelist.html")
		else:
			logging.info("User is not admin, cannot access whitelist")
			return redirect(url_for("index"))

def manage():
	tour = request.args.get('tour')
	cur_user = current_user()
	guestlist = []
	if cur_user:
		
		# Get message template
		msgTemplate = MessageTemplate.query(MessageTemplate.restaurant_key==cur_user.key,MessageTemplate.message_type==1,MessageTemplate.is_active==True).get()
		if not msgTemplate:
			# No template exists, create one
			msgTemplate = MessageTemplate(restaurant_key=cur_user.key,message_type=1,is_active=True,message_text="{firstName}, your table is almost ready. Need more time? Reply ""bump"" and the # of minutes you'd like.")
			msgTemplate.put()
		
		# Create a list of guests (as dicts) within the user's library
		for checkin in cur_user.get_checkedin_guests(): 
			guest = Guest.get_by_id(checkin.guest_key.id())
			checkedinGuest = {}
			checkedinGuest["guest_ID"] = checkin.guest_key.id()
			checkedinGuest["checkin_ID"] = checkin.key.id()
			checkedinGuest["firstName"] = guest.first_name
			checkedinGuest["lastName"] = guest.last_name
			if guest.sms_number:
				checkedinGuest["sms"] = functions.stylizePhoneNumber(guest.sms_number)
			checkedinGuest["email"] = guest.email
			checkedinGuest["partySize"] = checkin.party_size
			arrival_time = checkin.signin_time - timedelta(hours=6)
			checkedinGuest["arrival_time"] = arrival_time
			checkedinGuest["wait_estimate"] = checkin.wait_estimate
			checkedinGuest["target_time"] = arrival_time + timedelta(minutes=checkin.wait_estimate)
			guestlist.append(checkedinGuest)
	# Sort guestlist by arrival time (oldest on top)
	guestlist.sort(key=lambda guest: guest["arrival_time"])
	return render_response("manage.html", guestlist=guestlist, cur_user=cur_user, tour=tour, default_message=msgTemplate.message_text)

def advertise():
	cur_user = current_user()
	if not cur_user.is_demo:
		# Create a list of guests (as dicts) within the user's library
		optInList = []
		for guest in cur_user.get_optins():
			if guest.sms_number or guest.email:
				optin = {}
				optin["guest_ID"] = guest.key.id()
				if guest.first_name and guest.last_name:
					optin["name"] = guest.first_name + ' ' + guest.last_name
				elif guest.first_name:
					optin["name"] = guest.first_name
				#else:
				#	if guest.preferred_contact == 'sms':
				#		optin["name"] = guest.sms_number
				#	elif guest.preferred_contact == 'email':
				#		optin["name"] = guest.email
				#	else:
				#		# This should never be the case
				#		optin["name"] = "Unknown"
				if guest.preferred_contact == 'sms':
					optin["smsNumber"] = functions.stylizePhoneNumber(guest.sms_number)
				elif guest.preferred_contact == 'email':
					optin["email"] = guest.email
				if guest.subscribe_date:
					optin["subscribe_date"] = guest.subscribe_date.strftime('%m/%d/%y')
				else:
					optin["subscribe_date"] = "Unknown"
				if guest.signup_method:
					if guest.signup_method == 1:
						optin["signup_method"] = 'Waitlist'
					elif guest.signup_method == 2:
						optin["signup_method"] = 'SMS'
					elif guest.signup_method == 3:
						optin["signup_method"] = "Website"
				else:
					optin["signup_method"] = 'Waitlist'
				optin["promos_sent"] = Message.query(Message.restaurant_key==cur_user.key,Message.recipient_key==guest.key).count() # TODO: Don't count table notifications (it's going to be nasty to fix that!)
				optInList.append(optin)
		optInList.sort(key=lambda optin: optin["subscribe_date"])
		
		# Create list of MessageTemplates
		msgTemplates = []
		for msgTemplate in MessageTemplate.query(MessageTemplate.restaurant_key==cur_user.key,MessageTemplate.message_type==2,MessageTemplate.is_active==True).fetch():
			if msgTemplate.message_name: # If it doesn't have a name, we can't show it
				msg = {}
				msg["msgID"] = msgTemplate.key.id()
				msg["msgName"] = msgTemplate.message_name
				msg["msgText"] = msgTemplate.message_text
				msgTemplates.append(msg)
		msgTemplates.sort(key=lambda msg: msg["msgName"])
	else:
		return redirect(url_for("index"))
	return render_response("advertise.html", optInList=optInList, msgTemplates=msgTemplates)

def optin(user_ID=None):
	signup_method = request.args.get('signup_method')
	include_email = request.args.get('include_email')
	iframe = request.args.get('iframe')
	if not include_email:
		include_email = False
	elif include_email.lower() == "true":
		include_email = True
	else:
		include_email = False
	if not iframe:
		iframe = True
	elif iframe.lower() == "false":
		iframe = False
	else:
		iframe = True
	if not signup_method:
		signup_method = 3 # Default to website
	cur_user = current_user()
	if user_ID:
		# Regardless of who is logged in, send to page for provided user ID
		restaurant = UserAccount.get_by_id(int(user_ID))
	else:
		# No one is logged in, send to provided user or if none redirect to home
		if cur_user.is_authenticated():
			restaurant = cur_user
		else:
			return redirect(url_for("index")) 
	return render_response("optin.html",restaurant=restaurant,signup_method=signup_method,include_email=include_email,iframe=iframe)

def optin_guest(user_ID,signup_method):
	user = UserAccount.get_by_id(int(user_ID))
	# Opt in the guest (this will add them if they don't exist, and update and optin if they already do)
	guest = Guest.add_guest(firstName=request.form["firstName"], lastName=None, smsNumber=functions.digitizePhoneNumber(request.form["smsNumber"]), email=request.form["email"], preferredContact=request.form["preferredContact"], optIn=True, signup_method=int(signup_method), user=user)
	if guest:
		return "Success"
	else:
		return "Error"

def optout_guest(guest_ID):
	guest = Guest.get_by_id(int(guest_ID))
	if guest:
		guest.opt_in = False
		guest.put()
		return "Success"
	else:
		return "Error"

def undo_optout_guest(guest_ID):
	guest = Guest.get_by_id(int(guest_ID))
	if guest:
		guest.opt_in = True
		guest.put()
		return "Success"
	else:
		return "Error"

def new_promo():
	cur_user = current_user()
	templateName = request.form["templateName"]
	templateText = request.form["templateText"]
	msgTemplate = MessageTemplate(restaurant_key=cur_user.key,message_type=2,is_active=True,message_name=templateName,message_text=templateText)
	msgTemplate.put()
	return "Success"

def send_promos():
	
	sms_counter = 0
	
	if request.form["schedule"] == "now":
		msgTemplate = MessageTemplate.get_by_id(int(request.form["msgTemplate"]))
		
		# Nasty hack because I just don't get JSON
		for key in request.form:
			if key[:5] == "guest":
				# Send message
				Message.send_promo(request.form[key], msgTemplate)
				if Guest.get_by_id(int(request.form[key])).preferred_contact == 'sms':
					sms_counter = sms_counter + 1
					if sms_counter % 5 == 0:
					# Delay message 1 min with every 5 sms
						time.sleep(60)
	return "Success"

def update_party_size(checkin_ID):
	cur_user = current_user()
	if not cur_user:
		logging.info("there is not a user logged in")
		return "Error"
	else:
		checkin = CheckIn.get_by_id(int(checkin_ID))
		checkin.party_size = int(request.form["party-size"])
		checkin.put()
	return "Success"

def update_wait_estimate(checkin_ID):
	cur_user = current_user()
	if not cur_user:
		logging.info("there is not a user logged in")
		return "Error"
	else:
		checkin = CheckIn.get_by_id(int(checkin_ID))
		checkin.wait_estimate = int(request.form["wait-estimate"])
		target_seating_time = checkin.signin_time - timedelta(hours=6) + timedelta(minutes=checkin.wait_estimate)
		checkin.put()
	return jsonify({"target": target_seating_time.strftime('%I:%M %p')})

def quick_add():
	cur_user = current_user()
	if not cur_user:
		logging.info("there is not a user logged in")
		return "Error"
	else:
		# Create/Update Guest and Create New Checkin, adding to queue
		firstName = request.form["quickAddName"]
		try:
			# Not used anymore, but if neither SMS or Email is checked, this gives error
			preferredContact = request.form["preferredContact"]
		except:
			preferredContact = None
		# Check to see if a phone number or email was given
		quickAddContact = request.form["quickAddContact"]
		if quickAddContact == '':
			preferredContact = None # This causes email and smsNumber to be set to None later (even though it's passing an empty string)
		partySize = int(request.form["quickAddPartySize"])
		waitEstimate = int(request.form["quickAddWaitEstimate"])
		if preferredContact == 'sms':
			smsNumber = functions.digitizePhoneNumber(request.form["quickAddContact"])
			email = None
		elif preferredContact == 'email':
			email = request.form["quickAddContact"]
			smsNumber = None
		else:
			# email or smsNumber could be empty string, but set to none
			email = None
			smsNumber = None
		try:
			if request.form["quickAddOptIn"] == 'on':
				optIn = True
			else:
				optIn = False
		except:
			optIn = False
		guest = Guest.add_guest(firstName=firstName,lastName=None,preferredContact=preferredContact,smsNumber=smsNumber,email=email,optIn=optIn,signup_method=1,user=cur_user)
		if not guest:
			return "Error"
		checkin = CheckIn.check_in_guest(guest,partySize,waitEstimate)
		if not checkin:
			return "Error"
	return "Success"

def refresh_manage():
	cur_user = current_user()
	waitlist = []
	if cur_user:
	# Create a list of guests (as dicts) within the user's library
		for checkin in cur_user.get_checkedin_guests(): 
			guest = Guest.get_by_id(checkin.guest_key.id())
			checkedinGuest = {}
			checkedinGuest["guest_ID"] = checkin.guest_key.id()
			checkedinGuest["checkin_ID"] = checkin.key.id()
			checkedinGuest["firstName"] = guest.first_name
			checkedinGuest["lastName"] = guest.last_name
			if guest.sms_number:
				checkedinGuest["sms"] = functions.stylizePhoneNumber(guest.sms_number)
			checkedinGuest["email"] = guest.email
			checkedinGuest["partySize"] = checkin.party_size
			arrival_time = checkin.signin_time - timedelta(hours=6)
			checkedinGuest["arrival_time"] = arrival_time.strftime('%I:%M %p')
			checkedinGuest["wait_estimate"] = checkin.wait_estimate
			target_time = arrival_time + timedelta(minutes=checkin.wait_estimate)
			checkedinGuest["target_time"] = target_time.strftime('%I:%M %p')
			waitlist.append(checkedinGuest)
		# Sort guestlist by arrival time (oldest on top)
		waitlist.sort(key=lambda guest: guest["arrival_time"])
		jsondump = json.dumps(waitlist)
		return jsondump
	return "User Not Logged In"

def update_current_wait():
	cur_user = current_user()
	if not cur_user:
		logging.info("there is not a user logged in")
		return "Error"
	else:
		cur_user.default_wait = int(request.form["current-wait"])
		cur_user.put()
	return "Success"

def checkin_guest(checkin_ID):
	cur_user = current_user()
	if not cur_user:
		logging.info("there is not a user logged in")
		return "Error"
	else:
		checkin = CheckIn.get_by_id(int(checkin_ID))
		# Find checkin object and check in
		checkin.in_queue = False
		checkin.seat_time = datetime.datetime.now()
		wait_time_timedelta = checkin.seat_time - checkin.signin_time
		calculated_wait_time = float(wait_time_timedelta.seconds) / float(60)
		checkin.wait_time = calculated_wait_time
		checkin.put()
	return "Success"

def undo_checkin_guest(checkin_ID):
	cur_user = current_user()
	if not cur_user:
		logging.info("there is not a user logged in")
		return "Error"
	else:
		# Place CheckIn back in queue 
		checkin = CheckIn.get_by_id(int(checkin_ID))
		checkin.in_queue = True
		checkin.put()
	return "Success"
	
def send_default_msg(guest_ID):
	if Message.send_notification(guest_ID,False):
		return "Success"
	else:
		return "Error"

def send_custom_msg(guest_ID):
	if Message.send_notification(guest_ID,request.form["msg"]):
		return "Success"
	else:
		return "Error"
	
def reportbug():
	if request.method == 'POST' and "submitterName" in request.form and "submitterEmail" in request.form and "issueName" in request.form and "issueDescription" in request.form:
		title = request.form["issueName"]
		body = "Submitter Name: " + request.form["submitterName"] + "\nSubmitter Email: " + request.form["submitterEmail"] + "\nDescription:\n" + request.form["issueDescription"]
		labels = request.form["issueType"]
		import requests
		import json
		AUTH = ("bumpbot", "GitBumpB0t")
		GITHUB_URL = "https://api.github.com"
		HEADERS = {'Content-Type': 'application/json'}
		repo_owner = "natecarrier"
		repo = "bump"
		issues_url = "{0}/{1}".format(GITHUB_URL, "/".join(
				["repos", repo_owner, repo, "issues"]))
		data = {"title": title,
				"body": body,
				"labels": labels}
		requests.post(issues_url,
							 auth=AUTH,
							 headers=HEADERS,
							 data=json.dumps(data))
	
	return render_response('reportbug.html')
	
#def about():
#	return render_response('about.html')
	
#def join():
#	return render_response('join.html')

def login():
	g_user = users.get_current_user()
	if g_user:
		if login_account(g_user):
			# Login successful, send to manage page
			return redirect(url_for("manage"))
		else:
			# A user account has not yet been created for this google account, check whitelist then create
			if join_account(g_user):
				return redirect(url_for("manage"))
			else:
				return redirect(url_for("index") + '?whitelist=false')
	else:
		return redirect(users.create_login_url(request.url))

def demo_login():
	# Create demo account
	user = UserAccount(name="Bump Demo", email="demo@bumpapp.co", reply_to_email="demo@bumpapp.co", is_demo=True)
	user.put()
	if user and flasklogin.login_user(user,False):
		return redirect(url_for("manage") + '?tour=start')
	return redirect(url_for("index") + '?whitelist=false')
			
def logout():
	# Clear out guests and checkins if demo account
	cur_user = current_user()
	if cur_user.is_demo:
		# Delete guest objects, checkin objects, and user object
		guests = Guest.query(Guest.restaurant_key==cur_user.key).fetch()
		for guest in guests:
			checkins = CheckIn.query(CheckIn.guest_key==guest.key).fetch()
			for checkin in checkins:
				checkin.key.delete()
			guest.key.delete()
		for msg in Message.query(Message.restaurant_key==cur_user.key).fetch():
			msg.key.delete()
		for msgTemplate in MessageTemplate.query(MessageTemplate.restaurant_key==cur_user.key).fetch():
			msgTemplate.key.delete()
		cur_user.key.delete()
	# Logs out User
	logout_account()
	return redirect(users.create_logout_url("/"))

def open_source_licenses():
	return render_response('open-source-licenses.html')

######################## Internal calls (to be called by ajax) ##########################
def delete_user():
	cur_user = current_user()
	if not cur_user:
		logging.info("there is not a user logged in")
		#return "<a href='%s' >Login</a>" %users.create_login_url(dest_url=url_for('library_requests',ISBN=ISBN))
	if delete_account(cur_user):
		return "Success"
	return ""