import string
import random
import re
from schools.models import School

def random_salt(n=8):
    characterList = string.ascii_letters + string.digits
    salt = ['s']
    for i in range(n):
        randomchar = random.choice(characterList)
        salt.append(randomchar)
    return "".join(salt)


# Define a function for
# for validating an Email
def check_email(email):
    regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    # pass the regular expression
    # and the string into the fullmatch() method
    if (re.fullmatch(regex, email)):
        return True
    else:
        return False

def activate_users():
    schools=School.objects.all()
    for school in schools:
        for user in school.group.user_set.filter(is_active=False):
            user.is_active=True
            user.save()
    return True

def list_inactivate_users():
    schools=School.objects.all()
    for school in schools:
        for user in school.group.user_set.filter(is_active=False):
            print(school.name,user.name)
    return True