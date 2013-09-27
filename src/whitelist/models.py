from google.appengine.ext import ndb

class Whitelist(ndb.Model):
	domain = ndb.StringProperty(required=True)