# This file is for lazy loading urls with google app engine.
# It keeps a list of all the urls for the application and routes
# them to the appropriate functions in the views.py file.
#
# Lazy loading Info: http://flask.pocoo.org/docs/patterns/lazyloading/
#   We are only doing part of what is on this page. We are creating
#   a centralized URL map in this file and one of the functions is a
#   warmup function that loads the views into a new instance when google
#   app engine has to start up a new instance due to load increases. The example
#   on this url shows how to load in the view functions one at a time as needed.
#   Loading in one at a time will cause decorator problems, so to make things
#   easier, we are doing it like this.
#
# Warmup info: http://stackoverflow.com/questions/8235716/how-does-the-warmup-service-work-in-python-google-app-engine

from flask import Flask
from src import app, views, api
from views import render_response

# Warmup
app.add_url_rule('/_ah/warmup',view_func=views.warmup)

################################ Website landing pages ##################################
# Home page
app.add_url_rule('/',view_func=views.index,methods=["GET","POST"])

# Settings
app.add_url_rule('/settings',view_func=views.settings,methods=["GET","POST"])

# Login
app.add_url_rule('/login',view_func=views.login,methods=["GET","POST"])

# Join
#app.add_url_rule('/join',view_func=views.join)

# About
#app.add_url_rule('/about',view_func=views.about)

# Logout
app.add_url_rule('/logout',view_func=views.logout)

# Report a Bug
app.add_url_rule('/reportbug',view_func=views.reportbug,methods=["GET","POST"])

# Guest Sign In
app.add_url_rule('/guest-signin',view_func=views.guest_signin,methods=["GET","POST"])

# Whitelist
app.add_url_rule('/whitelist', view_func=views.whitelist,methods=["GET","POST"])

# Manage Guests
app.add_url_rule('/manage', view_func=views.manage,methods=["GET","POST"])

# Advertise
app.add_url_rule('/advertise', view_func=views.advertise,methods=["GET","POST"])

# Licenses
app.add_url_rule('/licenses', view_func=views.open_source_licenses)

# demo login
app.add_url_rule('/demo',view_func=views.demo_login)

######################## Internal calls (to be called by ajax) ##########################

# Check in Guest
app.add_url_rule('/checkin/<checkin_ID>',view_func=views.checkin_guest,methods=['GET'])

# Undo Guest Check in
app.add_url_rule('/undo_checkin/<checkin_ID>',view_func=views.undo_checkin_guest,methods=['GET'])

# Send Default Reminder
app.add_url_rule('/send_default/<guest_ID>',view_func=views.send_default_msg,methods=['GET'])

# Send Custom Reminder
app.add_url_rule('/send_custom/<guest_ID>', view_func=views.send_custom_msg,methods=['POST'])

# Delete the current user
app.add_url_rule('/delete',view_func=views.delete_user,methods=['GET'])

# Update party size
app.add_url_rule('/update_party_size/<checkin_ID>',view_func=views.update_party_size,methods=['GET','POST'])

# Update party size
app.add_url_rule('/update_wait_estimate/<checkin_ID>',view_func=views.update_wait_estimate,methods=['GET','POST'])

# Updates the current wait time
app.add_url_rule('/update_current_wait', view_func=views.update_current_wait,methods=['GET','POST'])

# Quick Add (Manage page)
app.add_url_rule('/quick_add', view_func=views.quick_add,methods=['GET','POST'])

# Refresh Manage
app.add_url_rule('/refresh_manage', view_func=views.refresh_manage,methods=['GET'])

# Create New Message Template for Promos
app.add_url_rule('/new_promo', view_func=views.new_promo,methods=['GET','POST'])

# Send coupons and promos
app.add_url_rule('/send_promos',view_func=views.send_promos,methods=['GET','POST'])


##################################### Error Handling ####################################
## Error Handlers
@app.errorhandler(404)
def page_not_found(e):
	return render_response('404error.html')

@app.errorhandler(500)
def server_error(e):
	return render_response('500error.html')