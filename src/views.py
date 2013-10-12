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
import logging
from decorators import crossdomain
from src import app
from utilities.JsonIterable import *
from accounts import login as login_account, logout as logout_account, join as join_account, delete as delete_account, current_user, login_required
from accounts.models import UserAccount
from google.appengine.api import mail
from datetime import date,timedelta
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
		
def settings():
	
	user = current_user()
	if user.demo_mode():
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
			if user.update(defaultMessage, promoDefault, gv_email, gv_password, reply_to_email):
				return "Success"
			else:
				return False
		return render_response('settings.html')
		
def guest_signin():
	cur_user = current_user()
	demo = request.args.get('demo')
	if cur_user:
		if request.method == 'POST':
			firstName = request.form["firstName"]
			lastName = request.form["lastName"]
			preferredContact = request.form["preferredContact"]
			if preferredContact == 'sms':
				smsNumber = request.form["smsNumber"]
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
			guest = Guest.add_guest(firstName=firstName,lastName=lastName,preferredContact=preferredContact,smsNumber=smsNumber,email=email,optIn=optIn)
			if not guest:
				return "Error"
			checkin = CheckIn.check_in_guest(guest)
			if not checkin:
				return "Error"
			if demo == "continue":
				return redirect(url_for("manage") + '?demo=continue')
			return "Success"
	return render_response("guest-signin.html", demo=demo)

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
	demo = request.args.get('demo')
	cur_user = current_user()
	guestlist = []
	if cur_user:
	# Create a list of guests (as dicts) within the user's library
		for checkin in cur_user.get_checkedin_guests():
			# Includes session_id, demo account (include only if session_id matches 
			guest = Guest.get_by_id(checkin.guest_key.id())
			if cur_user.demo_mode():
				demo_session_id = str(flasklogin.get_session_id())
			if "session_id" not in guest.to_dict():
				# Fix for old data
				guest.session_id = None
			if not guest.session_id or guest.session_id == demo_session_id:
				checkedinGuest = {}
				checkedinGuest["guest_ID"] = checkin.guest_key.id()
				checkedinGuest["checkin_ID"] = checkin.key.id()
				checkedinGuest["firstName"] = guest.first_name
				checkedinGuest["lastName"] = guest.last_name
				checkedinGuest["sms"] = guest.sms_number
				checkedinGuest["email"] = guest.email
				checkedinGuest["partySize"] = checkin.party_size
				arrival_time = checkin.signin_time - timedelta(hours=6)
				checkedinGuest["arrival_time"] = arrival_time
				checkedinGuest["wait_estimate"] = checkin.wait_estimate
				checkedinGuest["target_time"] = arrival_time + timedelta(minutes=checkin.wait_estimate)
				guestlist.append(checkedinGuest)
	# Sort guestlist by arrival time (oldest on top)
	guestlist.sort(key=lambda guest: guest["arrival_time"])
	return render_response("manage.html", guestlist=guestlist, cur_user=cur_user, demo=demo)	

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
			smsNumber = request.form["quickAddContact"]
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
		guest = Guest.add_guest(firstName=firstName,lastName=None,preferredContact=preferredContact,smsNumber=smsNumber,email=email,optIn=optIn)
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
			# Includes session_id, demo account (include only if session_id matches 
			guest = Guest.get_by_id(checkin.guest_key.id())
			if cur_user.demo_mode():
				demo_session_id = str(flasklogin.get_session_id())
			if "session_id" not in guest.to_dict():
				# Fix for old data
				guest.session_id = None
			if not guest.session_id or guest.session_id == demo_session_id:
				checkedinGuest = {}
				checkedinGuest["guest_ID"] = checkin.guest_key.id()
				checkedinGuest["checkin_ID"] = checkin.key.id()
				checkedinGuest["firstName"] = guest.first_name
				checkedinGuest["lastName"] = guest.last_name
				checkedinGuest["sms"] = guest.sms_number
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
	cur_user = current_user()
	guest = Guest.get_by_id(int(guest_ID))
	msg = cur_user.default_msg_ready
	msg = msg.replace('{firstName}',guest.first_name).replace('{lastName}',guest.last_name)
	if cur_user.demo_mode():
		msg = msg + " -- SENT BY BUMP DEMO: http://bumpapp.co"
	if guest.preferred_contact == 'email':
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
					body=msg)
	elif guest.preferred_contact == 'sms':
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
	return "Success"

def send_custom_msg(guest_ID):
	cur_user = current_user()
	guest = Guest.get_by_id(int(guest_ID))
	msg = request.form["msg"]
	if cur_user.demo_mode():
		msg = msg + " -- SENT BY BUMP DEMO: http://bumpapp.co"
	if guest.preferred_contact == 'email':
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
					body=msg)
	elif guest.preferred_contact == 'sms':
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
	return "Success"
	
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
	user = UserAccount.query(UserAccount.email=="demo@bumpapp.co").get()
	if not user:
		# If the demo account doesn't exist, create it.
		user = UserAccount(name="Bump Demo", email="demo@bumpapp.co")
		user.put()
	if user and flasklogin.login_user(user,False):
		return redirect(url_for("manage") + '?demo=start')
	return redirect(url_for("index") + '?whitelist=false')
			
def logout():
	# Clear out guests and checkins if demo account
	cur_user = current_user()
	if cur_user.demo_mode():
		guests = Guest.query(Guest.session_id==str(flasklogin.get_session_id())).fetch()
		for guest in guests:
			checkins = CheckIn.query(CheckIn.guest_key==guest.key).fetch()
			for checkin in checkins:
				checkin.key.delete()
			guest.key.delete()
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