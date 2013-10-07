################################### Web service calls ###################################
# Views
from flask import Response, jsonify, request
from accounts.models import UserAccount
from utilities.JsonIterable import *
import flaskext