"""
Байгууллагын албан аккаунтууд — хувь хүний биш:
  - сургуулийн удирдлага (School.manager, нэвтрэх нэр s0001 хэлбэртэй)
  - аймаг/дүүргийн удирдах ажилтан (Province.contact_person, нэвтрэх нэр padmin01 хэлбэртэй)

Нэр нь үргэлж сургууль/аймгийн нэрээс тогтоогдоно; хариуцаж буй хүн солигдоход зөвхөн
имэйл, утас шинэчлэгдэнэ.
"""
import re

SCHOOL_MANAGER_FIRST_NAME = 'Менежер'
PROVINCE_CONTACT_FIRST_NAME = 'Удирдах ажилтан'


def is_school_manager_account(user):
    return bool(re.match(r'^s\d{4}$', user.username or ''))


def is_province_contact_account(user):
    return (user.username or '').startswith('padmin')


def school_manager_names(school):
    """(first_name, last_name) — create_school_managers-ийн тогтоосон хэлбэр."""
    return SCHOOL_MANAGER_FIRST_NAME, f'{school.province.name} {school.name}'[:150]


def province_contact_names(province):
    return PROVINCE_CONTACT_FIRST_NAME, (province.name or '')[:150]


def apply_names(user, names):
    """Нэр өөрчлөгдсөн бол тохируулж True буцаана (хадгалахгүй)."""
    first_name, last_name = names
    if (user.first_name, user.last_name) == (first_name, last_name):
        return False
    user.first_name, user.last_name = first_name, last_name
    return True
