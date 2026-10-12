"""
Бүртгэгч багшид өдөрт нэг нэгдсэн имэйл: I давааны имэйлийн холбоосоор (round1_links)
сүүлийн 24 цагт ирсэн, батлагдаагүй хэвээр байгаа хүсэлтүүд.

Хүсэлт өөрөө сургуулийн «хүлээгдэж буй» жагсаалтад үлддэг тул нэг өдрийн мэдэгдэл
алдагдсан ч хүсэлт алдагдахгүй. Бүртгэгч багшгүй / имэйл хүрэхгүй сургуулийн хүсэлтийг
аймаг, дүүргийн админуудад илгээнэ.
"""
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from emails.html import text_email
from .models import EnrollmentLog
from .moderator import NOTICE_FROM_EMAIL, blocked_emails, email_problem, norm_email, province_admins
from .round1_links import REQUEST_NOTE

MAX_LISTED = 40


def pending_requests(since):
    """{school: [user]} — хугацаанд ирсэн, одоо ч батлагдаагүй хүсэлтүүд."""
    logs = (EnrollmentLog.objects.filter(action=EnrollmentLog.Action.REQUEST, note=REQUEST_NOTE,
                                         created_at__gte=since, to_school__isnull=False)
            .select_related('user__data__grade', 'to_school__user', 'to_school__province')
            .order_by('created_at'))
    by_school, seen = defaultdict(list), set()
    for log in logs:
        school, user = log.to_school, log.user
        if (school.pk, user.pk) in seen or not user.is_active:
            continue
        seen.add((school.pk, user.pk))
        meta = getattr(user, 'data', None)
        if meta is None or meta.school_id != school.pk:
            continue  # дараа нь сургуулиа сольсон
        if school.group_id and user.groups.filter(pk=school.group_id).exists():
            continue  # аль хэдийн батлагдсан
        by_school[school].append(user)
    return by_school


def digest_recipients(school, blocked):
    if school.user and email_problem(school.user, blocked) is None:
        return [school.user]
    return province_admins(school.province, blocked)


def build_digest(recipient, items):
    """items: [(school, [user])]."""
    total = sum(len(users) for _s, users in items)
    lines = [f'Сайн байна уу, {recipient.get_full_name().strip() or recipient.username}.', '',
             f'Сүүлийн 24 цагт {total} сурагч ММО-63-ын I давааны бүртгэлд орох хүсэлт илгээлээ. '
             'Сурагчид сургуулиа өөрсдөө сонгосон тул таны баталгаажуулалт хэрэгтэй.']
    for school, users in items:
        url = settings.SITE_URL + reverse('school_all_users', args=[school.pk])
        lines += ['', f'{school.name} ({len(users)}):']
        for u in users[:MAX_LISTED]:
            grade = getattr(getattr(u.data, 'grade', None), 'name', '') or ''
            lines.append(f'  - {u.last_name} {u.first_name} (ID {u.pk}{", " + grade if grade else ""})')
        if len(users) > MAX_LISTED:
            lines.append(f'  ... мөн {len(users) - MAX_LISTED}')
        lines.append(f'Батлах: {url}')
    lines += ['', 'Тухайн сургуулийн сурагч биш бол жагсаалтаас хасна уу.',
              'Асуух зүйл байвал registration@mmo.mn хаягаар холбогдоно уу.', '',
              'Математикийн олимпиадын хороо']
    subject = f'ММО-63 I даваа: {total} сурагчийн бүртгэлийн хүсэлт'
    return text_email(subject, '\n'.join(lines), NOTICE_FROM_EMAIL, [recipient.email])


def send_digests(now=None, hours=24, dry_run=False):
    """Хүлээн авагч бүрт нэг имэйл. [(хүлээн авагч, хүсэлтийн тоо)] буцаана."""
    now = now or timezone.now()
    blocked = blocked_emails()
    per_email, recipients = defaultdict(list), {}  # нэг хаяг руу нэг л имэйл
    for school, users in pending_requests(now - timedelta(hours=hours)).items():
        for r in digest_recipients(school, blocked):
            key = norm_email(r.email)
            recipients.setdefault(key, r)
            per_email[key].append((school, users))
    sent = []
    for key, items in per_email.items():
        recipient = recipients[key]
        msg = build_digest(recipient, items)
        if not dry_run:
            msg.send()
        sent.append((recipient, sum(len(u) for _s, u in items)))
    return sent
