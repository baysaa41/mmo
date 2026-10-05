"""
Сургуулийн бүртгэгч багш (School.user) солих үйлдэл ба мэдэгдэл.

Бүртгэгч багш солигдоход бие даасан хүнд мэдэгдэл очно:
  - сургуулийн удирдлага (manager) хуучин/шинэ багшаас өөр имэйлтэй бол удирдлагад,
  - үгүй бол аймаг/дүүргийн админуудад (contact_person, contact_person2, registrar, Province_{id}_Managers),
  - тэд ч имэйлгүй бол registration@mmo.mn руу.
"""
import logging
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from emails.html import text_email

logger = logging.getLogger(__name__)

NOTICE_FROM_EMAIL = 'registration@mmo.mn'
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_PLACEHOLDER_DOMAINS = ('example.com', 'example.org', 'test.com', 'localhost')


def norm_email(email):
    email = (email or '').strip().lower()
    if not _EMAIL_RE.match(email) or email.split('@')[1] in _PLACEHOLDER_DOMAINS:
        return ''
    return email


def blocked_emails():
    """Hard bounce, complaint болон татгалзсан (unsubscribe) имэйлүүд."""
    from emails.models import EmailBounce, EmailUnsubscribe
    blocked = {e.lower() for e in EmailBounce.objects.filter(
        bounce_type__in=['hard', 'complaint']).values_list('email', flat=True)}
    blocked |= {e.lower() for e in EmailUnsubscribe.objects.values_list('email', flat=True)}
    return blocked


# Энгийн хэрэглэгчид ойлгомжтой байхаар (bounce, unsubscribe гэх мэт техникийн нэр томьёогүй)
EMAIL_FAILED = 'имэйл хүргэхэд алдаа гарсан'
EMAIL_MISSING = 'имэйл бүртгэгдээгүй'
ACCOUNT_INACTIVE = 'аккаунт идэвхгүй'
ACCOUNT_MISSING = 'байхгүй'


def email_problem(user, blocked):
    """Хэрэглэгч рүү имэйл хүрэхгүй шалтгаан, хүрэх бол None.

    blocked нь hard bounce, complaint болон татгалзсан (unsubscribe) хаягууд — хэрэглэгчид
    бүгдийг нь "имэйл хүргэхэд алдаа гарсан" гэж харуулна.
    """
    if user is None:
        return ACCOUNT_MISSING
    if not user.is_active:
        return ACCOUNT_INACTIVE
    email = norm_email(user.email)
    if not email:
        return EMAIL_MISSING
    if email in blocked:
        return EMAIL_FAILED
    return None


def manager_has_own_email(school):
    """Удирдлага бүртгэгч багшаас өөр, хүчинтэй имэйлтэй эсэх."""
    manager_email = norm_email(school.manager.email) if school.manager else ''
    moderator_email = norm_email(school.user.email) if school.user else ''
    return bool(manager_email) and manager_email != moderator_email


def province_admins(province, blocked=frozenset()):
    if province is None:
        return []
    admins = {u for u in (*province.contact_persons, province.registrar) if u}
    admins |= set(User.objects.filter(groups__name=f'Province_{province.id}_Managers'))
    return [u for u in admins if email_problem(u, blocked) is None]


def change_moderator(school, new_moderator, changed_by):
    """Бүртгэгч багшийг сольж, commit болсны дараа мэдэгдэл илгээнэ."""
    old_moderator = school.user
    school.user = new_moderator
    school.save()
    if old_moderator != new_moderator:
        from .tasks import send_moderator_changed_notice_task
        args = [school.id, old_moderator.id if old_moderator else None, new_moderator.id,
                changed_by.id if changed_by else None, timezone.now().isoformat()]
        transaction.on_commit(lambda: send_moderator_changed_notice_task.delay(*args))


def send_moderator_changed_notice(school, old_moderator, new_moderator, changed_by, changed_at):
    """Мэдэгдэл илгээж, хүлээн авагчдын имэйлийн жагсаалтыг буцаана."""
    involved = {norm_email(u.email) for u in (old_moderator, new_moderator) if u}
    manager_email = norm_email(school.manager.email) if school.manager else ''

    blocked = blocked_emails()
    if manager_email and manager_email not in involved and manager_email not in blocked:
        audience, recipients = 'manager', [manager_email]
    else:
        # Удирдлага имэйлгүй, багштай ижил, эсвэл имэйл хүргэхэд алдаа гарсан → аймгийн админд
        audience = 'province'
        recipients = sorted({norm_email(u.email) for u in province_admins(school.province, blocked)}) or [NOTICE_FROM_EMAIL]

    body = render_to_string('schools/emails/moderator_changed.txt', {
        'school': school,
        'old': old_moderator,
        'new': new_moderator,
        'changed_by': changed_by,
        'changed_at': timezone.localtime(changed_at),
        'audience': audience,
        'site': settings.SITE_URL.rstrip('/'),
        'from_email': NOTICE_FROM_EMAIL,
    })
    text_email(
        subject=f'Анхааруулга: {school.name} сургуулийн бүртгэгч багш солигдлоо',
        body=body,
        from_email=NOTICE_FROM_EMAIL,
        to=recipients,
        reply_to=[NOTICE_FROM_EMAIL],
    ).send()
    logger.info('Moderator change notice for school %s sent to %s (%s)', school.id, recipients, audience)
    return recipients


def notify_account_email_changed(account, old_email, changed_by, organization, province):
    """Албан аккаунтын имэйл солигдсоныг commit болсны дараа хуучин хаяг руу мэдэгдэнэ."""
    if norm_email(old_email) == norm_email(account.email):
        return
    from .tasks import send_account_email_changed_notice_task
    args = [account.id, old_email or '', changed_by.id if changed_by else None, organization,
            province.id if province else None, timezone.now().isoformat()]
    transaction.on_commit(lambda: send_account_email_changed_notice_task.delay(*args))


def send_account_email_changed_notice(account, old_email, changed_by, organization, province, changed_at):
    """
    Хуучин имэйл рүү мэдэгдэл илгээнэ. Хуучин хаяг байхгүй эсвэл имэйл хүргэхэд алдаа гарсан бол
    аймгийн админд (эсвэл registration@mmo.mn руу) илгээнэ.
    """
    blocked = blocked_emails()
    old = norm_email(old_email)
    if old and old not in blocked:
        audience, recipients = 'old', [old]
    else:
        audience = 'province'
        recipients = sorted({norm_email(u.email) for u in province_admins(province, blocked)
                             if u.pk != account.pk}) or [NOTICE_FROM_EMAIL]

    body = render_to_string('schools/emails/account_email_changed.txt', {
        'account': account,
        'organization': organization,
        'old_email': old_email or 'бүртгэгдээгүй',
        'new_email': account.email,
        'changed_by': changed_by,
        'changed_at': timezone.localtime(changed_at),
        'audience': audience,
        'from_email': NOTICE_FROM_EMAIL,
    })
    text_email(
        subject=f'Анхааруулга: {organization} албан аккаунтын имэйл солигдлоо',
        body=body,
        from_email=NOTICE_FROM_EMAIL,
        to=recipients,
        reply_to=[NOTICE_FROM_EMAIL],
    ).send()
    logger.info('Account email change notice for user %s sent to %s (%s)', account.id, recipients, audience)
    return recipients
