# Views
from google.appengine.api import users
from flask import Response, jsonify, render_template, request, url_for, redirect, flash
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
			# First, check if guest is already in databases
			if cur_user.demo_mode():
				session_id = str(flasklogin.get_session_id())
			else:
				session_id = None
			if preferredContact == 'sms':
				if cur_user.demo_mode:
					guest = Guest.query(Guest.sms_number==smsNumber,Guest.restaurant_key==cur_user.key,Guest.session_id==session_id).get()
				else:
					guest = Guest.query(Guest.sms_number==smsNumber,Guest.restaurant_key==cur_user.key).get()
			elif preferredContact == 'email':
				if cur_user.demo_mode:
					guest = Guest.query(Guest.email==email,Guest.restaurant_key==cur_user.key,Guest.session_id==session_id).get()
				else:
					guest = Guest.query(Guest.email==email,Guest.restaurant_key==cur_user.key).get()
			if guest:
				# Update Guest in case info has changed
				guest.first_name = firstName
				guest.last_name = lastName
				guest.preferred_contact = preferredContact
				if not optIn:
					# If they've opted in previously and they didn't check now, leave opted in
					guest.opt_in = optIn
				guest.put()
				# See if guest is already in queue, if so overwrite
				checkin = CheckIn.query(CheckIn.guest_key==guest.key, CheckIn.restaurant_key==cur_user.key, CheckIn.in_queue==True).get()
				if checkin:
					checkin.last_name=lastName
					checkin.first_name=firstName
					checkin.signin_time=datetime.datetime.now()
				else:
					# Sign in Guest
					checkin = CheckIn(guest_key=guest.key, restaurant_key=cur_user.key, first_name=firstName, last_name=lastName, in_queue=True, signin_time =datetime.datetime.now())
			else:
				# Create New Guest
				if cur_user.demo_mode:
					guest = Guest(first_name=firstName, last_name=lastName, sms_number = smsNumber, email=email, preferred_contact=preferredContact, opt_in=optIn, restaurant_key=cur_user.key, session_id=session_id)
				else:
					guest = Guest(first_name=firstName, last_name=lastName, sms_number = smsNumber, email=email, preferred_contact=preferredContact, opt_in=optIn, restaurant_key=cur_user.key)
				if cur_user.demo_mode():
					guest.session_id = str(flasklogin.get_session_id())
				guest.put()
				# Sign in Guest
				checkin = CheckIn(guest_key=guest.key, restaurant_key=cur_user.key, first_name=firstName, last_name=lastName, in_queue=True, signin_time =datetime.datetime.now())
			checkin.put()
			if demo == "continue":
				# Hack to make sure name gets stored in database before page loads
				import time
				time.sleep(.15)
				return redirect(url_for("manage") + '?demo=continue')
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
		for record in cur_user.get_checkedin_guests():
			# Includes session_id, demo account (include only if session_id matches 
			guest = Guest.get_by_id(record.guest_key.id())
			if cur_user.demo_mode():
				demo_session_id = str(flasklogin.get_session_id())
			if "session_id" not in guest.to_dict():
				# Fix for old data
				guest.session_id = None
			if not guest.session_id or guest.session_id == demo_session_id:
				checkedinGuest = {}
				checkedinGuest["id"] = record.guest_key.id()
				checkedinGuest["checkin_ID"] = record.key.id()
				checkedinGuest["firstName"] = guest.first_name
				checkedinGuest["lastName"] = guest.last_name
				checkedinGuest["sms"] = guest.sms_number
				checkedinGuest["email"] = guest.email
				checkedinGuest["last_checkin"] = record.signin_time
				checkin_timestamp = record.signin_time - timedelta(hours=6)
				checkin_month = '0' + str(checkin_timestamp.month)
				checkin_month = checkin_month[-2:]
				checkin_day = '0' + str(checkin_timestamp.day)
				checkin_day = checkin_day[-2:]
				checkin_year = str(checkin_timestamp.year)
				if checkin_timestamp.hour <= 12: #TODO: 12am to 1am comes out as 00:30
					checkin_hour = '0' + str(checkin_timestamp.hour)
					checkin_hour = checkin_hour[-2:]
				else:
					checkin_hour = '0' + str(checkin_timestamp.hour - 12)
					checkin_hour = checkin_hour[-2:]
				if checkin_timestamp.hour <= 11:
					checkin_ampm = 'AM'
				else:
					checkin_ampm = 'PM'
				checkin_minute = '0' + str(checkin_timestamp.minute)
				checkin_minute = checkin_minute[-2:]
				checkedinGuest["checkin_date"] = checkin_month + '/' + checkin_day + '/' + checkin_year
				checkedinGuest["checkin_time"] = checkin_hour + ':' + checkin_minute + ' ' + checkin_ampm
				guestlist.append(checkedinGuest)
	# Sort itemlist alphabetically, with title as the primary sort key,
	# author as secondary, and item_subtype as tertiary
	guestlist.sort(key=lambda guest: guest["last_checkin"])
	# guestlist.sort(key=lambda item: item["author_director"].lower())
	# guestlist.sort(key=lambda item: item["title"].lower())
	return render_response("manage.html", guestlist=guestlist, cur_user=cur_user, demo=demo)	

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
	# Clear out guests if demo account
	cur_user = current_user()
	if cur_user.demo_mode():
		guests = Guest.query(Guest.session_id==str(flasklogin.get_session_id())).fetch()
		for guest in guests:
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