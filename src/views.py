# Views
from google.appengine.api import users
from flask import Response, jsonify, render_template, request, url_for, redirect, flash
from flaskext.login import login_required, login_user, logout_user
from googlevoice.voice import Voice
from googlevoice.util import input
from src.items.models import Item,ItemCopy
from src.guests.models import Guest
from src.checkins.models import CheckIn
from src.whitelist.models import Whitelist
from activity.models import RequestToBorrow, WaitingToBorrow
import logging
from decorators import crossdomain
from src import app
from utilities.JsonIterable import *
from accounts import login as login_account, logout as logout_account, join as join_account, delete as delete_account, current_user, login_required
from accounts.models import UserAccount
from activity.models import Action
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

@app.route("/tasks/item_due_reminders")
def item_due_reminders():
	count = 0
	"""find all the items due tomorrow and send reminder emails"""
	items = ItemCopy.query(ItemCopy.due_date==date.today() + timedelta(days=1)).fetch()
	for item in items:
		count += 1
		owner = UserAccount.query(UserAccount.key==item.owner).get()
		mail.send_mail(sender=owner.email,
			to=UserAccount.query(UserAccount.key==item.borrower).get().email,
			subject="Item Due Soon",
			body="""The following item is due to be returned tomorrow: '%s'.
			
Please return it to %s"""%(Item.query(Item.key==item.item).get().title,owner.name))
	return "%s reminders were sent out" %count

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
	
def library():
	# Create a list of items (as dicts) within the user's library
	itemlist = []
	useraccount = current_user()
	for copy in useraccount.get_library():
		item = Item.query(Item.key == copy.item).get().to_dict()
		item["item_subtype"] = copy.item_subtype
		item["escapedtitle"] = re.escape(item["title"])
		if copy.borrower is None:
			item["available"] = True
		else:
			item["available"] = False
		itemlist.append(item)
	# Sort itemlist alphabetically, with title as the primary sort key,
	# author as secondary, and item_subtype as tertiary
	itemlist.sort(key=lambda item: item["item_subtype"])
	itemlist.sort(key=lambda item: item["author_director"].lower())
	itemlist.sort(key=lambda item: item["title"].lower())
		
	return render_response('managelibrary.html', itemlist=itemlist)
	
def network():
	return render_response('network.html')
	
def discover():
	# Start by creating a list of items (as dicts) within the user's library
	# This is necessary prep to be able to show that the item is in the user's library
	librarylist = []
	useraccount = current_user()
	for copy in useraccount.get_library():
		item = Item.query(Item.key == copy.item).get().to_dict()
		item["item_subtype"] = copy.item_subtype
		item["escapedtitle"] = re.escape(item["title"])
		librarylist.append(item)
	
	# Create a list of all items (as dicts) in the user's network
	user = current_user()
	itemlist = []
	for connection in user.get_connections():
		u = UserAccount.getuser(connection.id())
		for copy in u.get_library():
			item = Item.query(Item.key == copy.item).get().to_dict()
			item["item_subtype"] = copy.item_subtype
			item["escapedtitle"] = re.escape(item["title"])
			if copy.borrower is None:
				item["available"] = True
			else:
				item["available"] = False
			# Check to see if book is in the user's library
			item["inLibrary"] = []
			for item_subtype in ['book', 'ebook', 'audiobook']:
				if (item["item_key"],item_subtype) in librarylist:
					item["inLibrary"].append(item_subtype)
			itemlist.append(item)
	
	# Sort itemlist alphabetically, with title as the primary sort key,
	# author as secondary, and item_subtype as tertiary
	itemlist.sort(key=lambda item: item["item_subtype"])
	itemlist.sort(key=lambda item: item["author_director"].lower())
	itemlist.sort(key=lambda item: item["title"].lower())
	
	#Remove duplicate books (dictionaries) from itemlist (list)
	dedupeditemlist = []
	for item in itemlist:
	  if item not in dedupeditemlist:
	    dedupeditemlist.append(item)
	
	return render_response('discover.html',itemlist=dedupeditemlist)
	
def search():
	itemlist = {}
	item_type = request.args.get('type')
	subtype_book = request.args.get('subtype_book')
	subtype_ebook = request.args.get('subtype_ebook')
	subtype_audiobook = request.args.get('subtype_audiobook')
	searchterm = request.args.get('query')
	attr = request.args.get('refineSearch')
	
	subtype_specified = "true" # Used in javascript to determine whether out-of-network cookie should be respected or not
	
	if subtype_book or subtype_ebook or subtype_audiobook:
		# If subtype is included, item_type is not, so it must be added
		item_type = "book"
	else:
		# None are included, so only item_type is being pass; set all subtypes to true
		subtype_specified = "false"
		subtype_book = "true"
		subtype_ebook = "true"
		subtype_audiobook = "true"
	
	if attr == "all":
		attr = None
	
	if searchterm is None:
		searchterm = ""
	else:
		searchterm = searchterm.lstrip()
		
	if searchterm is None or searchterm == "":
		pass
	else:
		cur_user = current_user()
		logging.info(cur_user)
		if not cur_user.is_authenticated():
			#Assume no books in library or network, return results only
			itemlist = Item.search_by_attribute("book",searchterm,attr)
			for item in itemlist:
				item["inLibrary"] = []
				item["inNetwork"] = "False"
		
		else:
			user = current_user()
			
			#Create a dictionary of the user's books
			librarylist = {}
			for copy in user.get_library():
				copyItemKey = Item.query(Item.key == copy.item).get().item_key
				copyItemSubtype = copy.item_subtype
				librarylist[(copyItemKey,copyItemSubtype)] = copy.to_dict()
				
			#Create a dictionary of the items in the user's network
			#The dict, networkitemlist, includes each ItemCopy object, with it's associated item_key.
			networkitemlist = {}
			for connection in user.get_connections():
				u = UserAccount.getuser(connection.id())
				for copy in u.get_library():
					copyItemKey = Item.query(Item.key == copy.item).get().item_key
					copyItemSubtype = copy.item_subtype
					networkitemlist[(copyItemKey,copyItemSubtype)] = copy.to_dict()

			itemlist = Item.search_by_attribute("book",searchterm,attr)
			for item in itemlist:
				item["escapedtitle"] = re.escape(item["title"])
				
				# Check for copies in library and in network, 
				# return "inLibrary" list with all item types in Library
				# return "inNetwork" list with all item types in Library
				item["inLibrary"] = []
				item["inNetwork"] = []
				for item_subtype in ['book', 'ebook', 'audiobook']:
					if (item["item_key"],item_subtype) in librarylist:
						item["inLibrary"].append(item_subtype)
					if (item["item_key"],item_subtype) in networkitemlist:
						item["inNetwork"].append(item_subtype)
				
	return render_response('search.html', itemlist=itemlist, search=searchterm, attribute=attr, include_type=item_type, subtype_book=subtype_book, subtype_ebook=subtype_ebook, subtype_audiobook=subtype_audiobook, subtype_specified=subtype_specified)
	
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
			if preferredContact == 'sms':
				guest = Guest.query(Guest.sms_number==smsNumber,Guest.restaurant_key==cur_user.key).get()
			elif preferredContact == 'email':
				guest = Guest.query(Guest.email==email,Guest.restaurant_key==cur_user.key).get()
			if guest:
				# Update Guest in case info has changed
				guest.first_name = firstName
				guest.last_name = lastName
				guest.preferred_contact = preferredContact
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
				guest = Guest(first_name=firstName, last_name=lastName, sms_number = smsNumber, email=email, preferred_contact=preferredContact, opt_in=optIn, restaurant_key=cur_user.key)
				if cur_user.demo_mode():
					from flaskext import login as flasklogin
					guest.session_id = str(flasklogin.get_session_id())
				guest.put()
				# Sign in Guest
				checkin = CheckIn(guest_key=guest.key, restaurant_key=cur_user.key, first_name=firstName, last_name=lastName, in_queue=True, signin_time =datetime.datetime.now())
			checkin.put()
			if demo == "continue":
				# Hack to make sure name gets stored in database before page loads
				import time
				time.sleep(.05)
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
			from flaskext import login as flasklogin
			demo_session_id = str(flasklogin.get_session_id())
			if "session_id" not in guest.to_dict():
				# Fix for old data
				guest.session_id = None
			if not guest.session_id or guest.session_id == demo_session_id:
				checkedinGuest = {}
				checkedinGuest["id"] = record.guest_key.id()
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

def checkin_guest(guest_ID):
	cur_user = current_user()
	if not cur_user:
		logging.info("there is not a user logged in")
		return "Error"
	else:
		guest = Guest.get_by_id(int(guest_ID))
		# Find checkin object and check in
		checkin = CheckIn.query(CheckIn.guest_key==guest.key, CheckIn.restaurant_key==cur_user.key, CheckIn.in_queue==True).get()
		checkin.in_queue = False
		checkin.seat_time = datetime.datetime.now()
		wait_time_timedelta = checkin.seat_time - checkin.signin_time
		checkin.wait_time = wait_time_timedelta.seconds / 60 
		checkin.put()
	return "Success"

def undo_checkin_guest(guest_ID):
	cur_user = current_user()
	if not cur_user:
		logging.info("there is not a user logged in")
		return "Error"
	else:
		# Find most recent checkin
		# TODO: .order() is not re-ordering propertly. Needs fix to return CheckIn of most recent signin_time
		checkin = CheckIn.query(CheckIn.guest_key==Guest.get_by_id(int(guest_ID)).key).order(CheckIn.signin_time).get()
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
	
def about():
	return render_response('about.html')
	
def mobile_app():
	return render_response('mobileapp.html')

@login_required
def profile(userID):
	profile_user = UserAccount.get_by_id(int(userID))
	user = current_user()
	if not profile_user:
		return render_response('invalidprofile.html')
	if user.is_connected(profile_user):
		library = []
		for copy in profile_user.get_library():
			item = Item.query(Item.key == copy.item).get().to_dict()
			item["item_subtype"] = copy.item_subtype
			item["escapedtitle"] = re.escape(item["title"])
			if copy.borrower is None:
				item["available"] = True
			else:
				item["available"] = False
			item["copyID"] = copy.key.id()
			library.append(item)
			
		# Sort library alphabetically, with title as the primary sort key,
		# author as secondary, and item_subtype as tertiary
		library.sort(key=lambda item: item["item_subtype"])
		library.sort(key=lambda item: item["author_director"].lower())
		library.sort(key=lambda item: item["title"].lower())
		return render_response('profile.html',profile_user=profile_user,library=library)
	return render_response('invalidprofile.html')
	
#def book_info():
	# Pass book object to template
	#return render_response('bookinfo.html')
	
def join():
	return render_response('join.html')

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
	user = UserAccount.get_by_email('demo@bumpapp.co')
	from flaskext import login as flasklogin
	if user and flasklogin.login_user(user,False):
		return redirect(url_for("manage") + '?demo=start')
	return redirect(url_for("index") + '?whitelist=false')
			
def logout():
	# Clear out guests if demo account
	cur_user = current_user()
	if cur_user.demo_mode():
		from flaskext import login as flasklogin
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

def library_requests(item_subtype, item_key):
	cur_user = current_user()
	if not cur_user:
		logging.info("there is not a user logged in")
		#return "<a href='%s' >Login</a>" %users.create_login_url(dest_url=url_for('library_requests',ISBN=ISBN))
		
	if request.method == 'GET':
		#check the database to see if the item is in the user's library
		item = Item.get_by_key(item_key)
		if item:
			if cur_user.get_book(item_subtype,item):
				return item.title
			else:
				return "You do not have this item in your library"
		else:
			return "This item was not found"
	elif request.method == 'POST':
		#add the item to the user's library
		#If not found, add it to the cache, then to the user's library
		item = Item.get_by_key(item_key)

		if not item:
			return "Item " + item_key + " was not found"
		else:
			if cur_user.get_item(item_subtype,item):
				return "This item is already in your library"
			cur_user.add_item(item_subtype, item)
			return "Item " + item_key + " was added to your library"
	elif request.method == 'DELETE':	
		#remove the item from the user's library
		item = Item.get_by_key(item_key)
		if not item:
			return "Item not found"
		else:
			if cur_user.get_item(item_subtype,item):
				cur_user.remove_item(item_subtype,item)
			return "Successfully deleted " + item_key + " from your library"
	else:
		#this should never be reached
		return "Error: http request was invalid"

def get_my_item_list():
	cur_user = current_user()
	if not cur_user:
		logging.info("there is not a user logged in")
		return "<a href='%s' >Login</a>" %users.create_login_url(dest_url=url_for('manage_library'))

	items = {}
	counter = 0
	for copy in cur_user.get_library():
		item = Item.query(Item.key == copy.item).get()
		items[counter] = item.to_dict()
		counter += 1
	return jsonify(JsonIterable.dict_of_dict(items))

def search_for_book(value, attribute=None):
	# This is broken because search_books_by_attribute now returns a list of dicts
	books = Item.search_by_attribute("book",value,attribute)
	if len(books) == 0:
		return jsonify({"Message":"No books found"})
	else:
		return jsonify(JsonIterable.dict_of_dict(books))

def manage_connections(otherUserID = None):
	cur_user = current_user()

	if request.method == 'GET':
		connections = cur_user.get_all_connections()
		users = []
		result = "you have " + str(len(connections)) + " connections"
		for connection in connections:
			result += "<br>" + connection.name
			user = dict()
			user["name"] = connection.name
			user["email"] = connection.email
			#user["username"] = connection.username
			user["id"] = connection.get_id()
			users.append(user)
		return jsonify({"connectedUsers":users})
	elif request.method == 'POST':
		cur_user = current_user()
		otherUser = UserAccount.getuser(int(otherUserID))
		result = cur_user.send_invite(otherUser)
		if(result == 0):
			return jsonify({"Message":"Invitation successfully sent"})
		elif(result == 1):
			return jsonify({"Message":"Connection already existed"})
		elif(result == 2):
			return jsonify({"Message":"Cannot create a connection with yourself"})
	elif request.method == 'DELETE':
		cur_user = current_user()
		otherUser = UserAccount.getuser(int(otherUserID))
		if cur_user.remove_connection(otherUser):
			return jsonify({"Message":"Connection successfully deleted"})
		else:
			return jsonify({"Message":"Connection didn't existed"})
	else:
		#this should never be reached
		return jsonify({"Message":"Error: http request was invalid"})
		
def simple_add_connection(otherUserID):
	cur_user = current_user()
	otherUser = UserAccount.getuser(int(otherUserID))
	if cur_user.add_connection(otherUser):
		return jsonify({"Message":"Connection successfully created"})
	else:
		return jsonify({"Message":"Connection already existed"})

def lend_item(itemCopyID, borrowerID, due_date = None):
	cur_user = current_user()
	return cur_user.lend_item(int(itemCopyID), int(borrowerID), due_date)

def borrow_item(itemCopyID, lenderID, due_date = None):
	cur_user = current_user()
	return cur_user.borrow_item(int(itemCopyID), int(lenderID), due_date)

def get_lent_items():
	cur_user = current_user()
	lentItems = []
	for itemcopy in cur_user.get_lent_books():
		item = Item.get_by_id(itemcopy.item.id())
		borrower = UserAccount.get_by_id(itemcopy.borrower.id())
		itemInfo = dict()
		itemInfo["title"] = item.title
		itemInfo["author_director"] = item.author_director
		itemInfo["copyID"] = itemcopy.key.id()
		itemInfo["borrowerId"] = itemcopy.borrower.id()
		itemInfo["borrower"] = borrower.name
		itemInfo["due_date"] = str(itemcopy.due_date)
		itemcopy.append(itemInfo)
	return jsonify({"lentItems":itemcopy})

def get_borrowed_items():
	cur_user = current_user()
	borrowedItems = []
	for itemcopy in cur_user.get_borrowed_books():
		item = Item.get_by_id(itemcopy.item.id())
		owner = UserAccount.get_by_id(itemcopy.owner.id())
		itemInfo = dict()
		itemInfo["title"] = item.title
		itemInfo["author_director"] = item.author_director
		itemInfo["copyID"] = itemcopy.key.id()
		itemInfo["ownerId"] = itemcopy.owner.id()
		itemInfo["owner"] = owner.name
		itemInfo["due_date"] = str(itemcopy.due_date)
		borrowedItems.append(itemInfo)
	return jsonify({"borrowedItems":borrowedItems})

def return_item(itemCopyID):
	cur_user = current_user()
	result = cur_user.return_item(itemCopyID)
	return jsonify({"Message":result})

def change_due_date(itemCopyID, newDueDate):
	cur_user = current_user()
	result = cur_user.change_due_date(itemCopyID, newDueDate)
	return jsonify({"Message":result})	
	
def search_network(item_key):
	user = current_user()

	networkuserlist = {}
	for connection in user.get_connections():
		u = UserAccount.getuser(connection.id())
		for copy in u.get_library():
			if Item.query(Item.key == copy.item).get().item_key == item_key:
				user = {}
				user["username"] = u.name
				user["itemCopyID"] = copy.key.id()
				if copy.borrower == None:
					user["available"] = "True"
				else:
					user["available"] = "False"
				networkuserlist[u.get_id()] = user

	return jsonify(networkuserlist)
	
def setup_item_borrow_actions(lenderID, itemCopyID):
	borrower = current_user()
	lender = UserAccount.getuser(int(lenderID))
	itemCopy = ItemCopy.get_by_id(int(itemCopyID))
	
	rtb1 = RequestToBorrow()
	rtb1.useraccount = lender.key
	rtb1.connection = borrower.key
	rtb1.item = itemCopy.key
	rtb1.put()
	
	wtb1 = WaitingToBorrow()
	wtb1.useraccount = borrower.key
	wtb1.connection = lender.key
	wtb1.item = itemCopy.key
	wtb1.put()
	return jsonify({"Message":"OK"})


def get_notifications():
	cur_user = current_user()
	notifications = []
	for notification in cur_user.pending_actions:
		info = dict()
		info["ID"] = notification.key.id()
		info["text"] = notification.text
		info["confirm_text"] = notification.accept_text
		info["confirm_activated"] = notification.can_accept
		info["reject_text"] = notification.reject_text
		info["reject_activated"] = notification.can_reject
		notifications.append(info)
	return jsonify({"notifications": notifications})

def confirm_notification(notificationID):
	action = Action.get_by_id(int(notificationID))
	result = action.confirm()
	return result

def reject_notification(notificationID):
	action = Action.get_by_id(int(notificationID))
	result = action.reject()
	return result