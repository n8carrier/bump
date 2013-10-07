from models import UserAccount
from src.whitelist.models import Whitelist
from flaskext import login as flasklogin
import logging

def join(account, remember=False):
	# If this is the first user account, then allow to create and make admin
	users = UserAccount.query().fetch()
	if not users:
		logging.info("First user account, creating user as admin", account._User__email)
		user = UserAccount.create_user(account,make_admin=True)
		if user and flasklogin.login_user(user, remember):
			return True
	# First check domain in whitelist
	domain = account._User__email[account._User__email.index('@')+1:]
	logging.info("Checking domain %s for whitelist", domain)
	whitelistUser = Whitelist.query(Whitelist.domain==domain.lower()).get()
	if whitelistUser:
		logging.info("Domain %s is whitelisted, creating user account %s", domain, account._User__email)
		user = UserAccount.create_user(account)
		if user and flasklogin.login_user(user, remember):
			return True
	else:
		# Domain not in whitelist, check email address
		logging.info("Checking email address %s for whitelist", account._User__email)
		whitelistUser = Whitelist.query(Whitelist.domain==account._User__email.lower()).get()
		if whitelistUser:
			logging.info("Email address %s is whitelisted, creating user account", account._User__email)
			user = UserAccount.create_user(account)
			if user and flasklogin.login_user(user, remember):
				return True
	return False

def login(account, remember=False):
	email = account.email()
	user = UserAccount.get_by_email(email)
	if user and flasklogin.login_user(user, remember):
		return True
	return False

def logout():
	flasklogin.logout_user()

def delete(user):
	if UserAccount.can_delete_user(user):
		return UserAccount.delete_user(user)
	return None

def current_user():
	return flasklogin.current_user

login_required = flasklogin.login_required

