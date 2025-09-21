import string
import random
from schools.models import School

import re
import unicodedata

def normalize_name(name: str) -> str:
    if not name:
        return ''

    # Юникод normalize (ё → е, ü → u гэх мэт)
    n = unicodedata.normalize('NFKD', name).lower()

    # кирилл үсгийг латинтай адилтгах (жишээ):
    n = n.replace('ё','е').replace('ү','у').replace('ө','о')

    # латин үсгийг кирилл рүү ойролцоогоор хөрвүүлэх (хүссэнээрээ нэмэж болно)
    latin_map = {
        'a':'а','b':'б','v':'в','g':'г','d':'д','e':'е','j':'ж','z':'з','i':'и',
        'k':'к','l':'л','m':'м','n':'н','o':'о','p':'п','r':'р','s':'с','t':'т',
        'u':'у','f':'ф','h':'х','c':'ц','y':'й'
    }
    for latin, cyr in latin_map.items():
        n = re.sub(rf'\b{latin}\b', cyr, n)  # ганц үсэгтэй үг

    # '1-р сургууль' гэх мэт тоог '1' болгож ерөнхий болгох
    n = re.sub(r'(\d+)(-р)?', r'\1', n)

    # 'ЕБС', 'EBS', 'school', 'surguuli' зэрэг түгээмэл үгсийг хасах
    stop_words = ['ебс', 'ebs', 'school', 'surguuli', 'surguul', 'сургууль']
    for w in stop_words:
        n = n.replace(w, '')

    # илүү зай, тэмдэг арилгах
    n = re.sub(r'\s+', ' ', n)
    return n.strip()


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

def list_inactive_users():
    schools=School.objects.all()
    for school in schools:
        for user in school.group.user_set.filter(is_active=False):
            print(school.name,user.username)
    return True