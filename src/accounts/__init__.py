from models import UserAccount
from src.whitelist.models import Whitelist
from flaskext import login as flasklogin
import logging

def join(account, remember=False):
	# First check domain in whitelist
	domain = account._User__email[account._User__email.index('@')+1:]
	whitelistUser = Whitelist.query(Whitelist.domain==domain).get()
	if whitelistUser:
		user = UserAccount.create_user(account)
		if user and flasklogin.login_user(user, remember):
			return True
	else:
		# Domain not in whitelist, check email address
		whitelistUser = Whitelist.query(Whitelist.domain==account._User__email).get()
		if whitelistUser:
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

