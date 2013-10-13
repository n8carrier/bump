# Functions
import re

def digitizePhoneNumber(phoneNumber): 
    # Remove everything but numeric digits 
    digitizedNumber = re.sub("\D", "", phoneNumber)
    # If it starts with a 1 and is 11 digits, strip it off
    if len(digitizedNumber) == 11:
        if digitizedNumber[:1] == 1:
            digitizedNumber = digitizedNumber[1:]
    return digitizedNumber

def stylizePhoneNumber(digitizedPhoneNumber):
    # Converts phone number in 5555555555 to (555) 555-5555
    # Verify phone number is in proper format, otherwise digitize it first
    if digitizedPhoneNumber != re.sub("\D", "", digitizedPhoneNumber) or len(digitizedPhoneNumber) != 10:
        digitizedPhoneNumber = digitizePhoneNumber(digitizedPhoneNumber)
    stylizedPhoneNumber = '(' + digitizedPhoneNumber[0:3] + ') ' + digitizedPhoneNumber[3:6] + '-' + digitizedPhoneNumber[6:10]
    return stylizedPhoneNumber