"""
Өөрөө бүртгүүлсэн (django-registration) хэрэглэгчийн идэвхжүүлэх имэйл.

Бүртгүүлэх үед болон «Идэвхжүүлэх холбоос дахин авах» хуудаснаас хоёуланд нь
ашиглана. Нэг аккаунт руу богино хугацаанд олон удаа илгээхгүйн тулд cache-ээр
хязгаарлана.
"""
import logging

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.urls import reverse
from django_registration.backends.activation.views import REGISTRATION_SALT

from emails.html import REGISTRATION_FROM_EMAIL, text_email
from emails.suppression import is_undeliverable

logger = logging.getLogger(__name__)

RESEND_COOLDOWN_SECONDS = 5 * 60


def pending_activation_users():
    """Имэйлээ баталгаажуулаагүй (нэг ч удаа нэвтрээгүй, идэвхгүй) хэрэглэгчид.
    Админ идэвхгүй болгосон хуучин аккаунтыг last_login-оор нь ялгана."""
    from django.contrib.auth.models import User
    return User.objects.filter(is_active=False, last_login__isnull=True)


def activation_url(request, user):
    key = signing.dumps(obj=user.get_username(), salt=REGISTRATION_SALT)
    path = reverse('django_registration_activate', kwargs={'activation_key': key})
    return f'https://{request.get_host()}{path}'


def _cooldown_key(user):
    return f'activation_email_sent:{user.pk}'


def recently_sent(user):
    return cache.get(_cooldown_key(user)) is not None


def send_activation_email(request, user):
    """Идэвхжүүлэх холбоосыг нэг имэйлээр илгээнэ. Илгээсэн бол True.

    Өмнө нь hard bounce хийсэн хаяг руу илгээхгүй (SES-ийн bounce хувийг
    өсгөхөөс сэргийлнэ); cooldown-ийг тавьсан хэвээр үлдээж, давтан
    дарахад дахин шалгахгүй.
    """
    if is_undeliverable(user.email):
        logger.warning('Activation email skipped (undeliverable address): user_id=%s', user.pk)
        cache.set(_cooldown_key(user), 1, RESEND_COOLDOWN_SECONDS)
        return False
    days = settings.ACCOUNT_ACTIVATION_DAYS
    body = (
        'Сайн байна уу,\n\n'
        f'Та mmo.mn сайтад «{user.get_username()}» нэвтрэх нэрээр бүртгүүлсэн байна. '
        'Бүртгэлээ идэвхжүүлэхийн тулд доорх холбоос дээр дарна уу:\n\n'
        f'{activation_url(request, user)}\n\n'
        f'Холбоос {days} хоногийн турш хүчинтэй. Идэвхжүүлсний дараа дээрх нэвтрэх нэр, '
        'бүртгүүлэхдээ оруулсан нууц үгээрээ нэвтэрнэ.\n\n'
        'Хэрэв та бүртгүүлээгүй бол энэ имэйлийг тоохгүй орхино уу.\n\n'
        'Монголын Математикийн Олимпиадын Хороо\n'
        'mmo.mn'
    )
    text_email('mmo.mn: бүртгэлээ идэвхжүүлнэ үү', body,
               REGISTRATION_FROM_EMAIL, [user.email]).send()
    cache.set(_cooldown_key(user), 1, RESEND_COOLDOWN_SECONDS)
    return True
