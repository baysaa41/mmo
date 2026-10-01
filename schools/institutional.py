"""
Байгууллагын албан аккаунтууд — хувь хүний биш:
  - сургуулийн удирдлага (School.manager, нэвтрэх нэр s0001 хэлбэртэй)
  - аймаг/дүүргийн удирдах ажилтан (Province.contact_person, нэвтрэх нэр padmin01 хэлбэртэй)

Нэр нь үргэлж сургууль/аймгийн нэрээс тогтоогдоно; хариуцаж буй хүн солигдоход зөвхөн
имэйл, утас шинэчлэгдэнэ.
"""
import re

SCHOOL_MANAGER_FIRST_NAME = 'Менежер'
# Сургуулийн удирдлагын аккаунтын эзэмшигч өөрийн албан тушаалыг сонгоно (first_name-д хадгална)
SCHOOL_MANAGER_ROLES = ['Захирал', 'Менежер', 'Бусад']
PROVINCE_CONTACT_FIRST_NAME = 'Удирдах ажилтан'


def is_school_manager_account(user):
    return bool(re.match(r'^s\d{4}$', user.username or ''))


def is_province_contact_account(user):
    return (user.username or '').startswith('padmin')


def school_manager_names(school, role=None):
    """(first_name, last_name): овог нь "{аймаг} {сургууль}", нэр нь сонгосон албан тушаал.

    Албан тушаал жагсаалтад байхгүй (хувь хүний нэр гэх мэт) бол "Менежер".
    """
    first_name = role if role in SCHOOL_MANAGER_ROLES else SCHOOL_MANAGER_FIRST_NAME
    return first_name, f'{school.province.name} {school.name}'[:150]


def province_contact_names(province):
    return PROVINCE_CONTACT_FIRST_NAME, (province.name or '')[:150]


def apply_names(user, names):
    """Нэр өөрчлөгдсөн бол тохируулж True буцаана (хадгалахгүй)."""
    first_name, last_name = names
    if (user.first_name, user.last_name) == (first_name, last_name):
        return False
    user.first_name, user.last_name = first_name, last_name
    return True
