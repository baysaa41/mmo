"""
Сурагчдыг сургууль хооронд шилжүүлэх хүсэлтийн service.

Урсгал:
  1. Илгээгч сургууль (бүртгэгч багш/менежер) сурагчдаа сонгоод хүлээн
     авах сургуулийг заана → request_transfers() хүлээгдэж буй хүсэлт үүсгэнэ.
  2. Хүлээн авагч сургууль accept()/reject() хийнэ. accept нь
     enrollment.enroll()-ээр сурагчийг шилжүүлнэ (EnrollmentLog-д TRANSFER).
  3. Шийдвэр гарахаас өмнө илгээгч cancel() хийж болно.

Шийдвэр гартал сурагч хуучин сургуульдаа үлдэх тул олимпиадаас хоцрохгүй.
Сургууль хоёр хуваагдах үед олон сурагчийг нэг дор шилжүүлэхэд ч ашиглана.
"""
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from emails.html import text_email

from . import enrollment
from .models import StudentTransfer

logger = logging.getLogger(__name__)

Status = StudentTransfer.Status


def transfer_block_reason(user, from_school, to_school, *, by):
    """Шилжүүлэх боломжгүй бол шалтгааныг, боломжтой бол None буцаана."""
    if to_school.pk == from_school.pk:
        return 'ижил сургууль'
    if not to_school.group_id:
        return 'хүлээн авах сургуулийн бүлэг тохируулагдаагүй'
    if not from_school.group_id or not user.groups.filter(pk=from_school.group_id).exists():
        return 'энэ сургуульд бүртгэлгүй'
    if user.is_superuser or (user.is_staff and not by.is_staff):
        return 'админ хэрэглэгч'
    if user.moderating.exists() or user.managing.exists():
        return 'сургуулийн бүртгэгч багш/менежер'
    if StudentTransfer.objects.filter(user=user, status=Status.PENDING).exists():
        return 'өөр шилжүүлгийн хүсэлт хүлээгдэж байна'
    return None


def request_transfers(users, from_school, to_school, *, by, note=''):
    """
    Сурагч бүрт хүлээгдэж буй хүсэлт үүсгэнэ.
    (үүссэн хүсэлтүүд, [(user, шалтгаан), ...] алгассан) буцаана.
    """
    created, skipped = [], []
    for user in users:
        reason = transfer_block_reason(user, from_school, to_school, by=by)
        if reason:
            skipped.append((user, reason))
            continue
        try:
            with transaction.atomic():
                created.append(StudentTransfer.objects.create(
                    user=user, from_school=from_school, to_school=to_school,
                    requested_by=by, note=note[:255],
                ))
        except IntegrityError:  # зэрэг илгээсэн хүсэлт
            skipped.append((user, 'өөр шилжүүлгийн хүсэлт хүлээгдэж байна'))
    return created, skipped


def _decide(transfer_id, school, status, by):
    """
    school-д хамаарах хүлээгдэж буй хүсэлтийг түгжиж, төлөвийг солино.
    Хүлээгдэж буй биш бол None.
    """
    lookup = {'to_school': school} if status != Status.CANCELLED else {'from_school': school}
    t = (StudentTransfer.objects.select_for_update(of=('self',))
         .select_related('user', 'from_school__group', 'to_school__group')
         .filter(pk=transfer_id, status=Status.PENDING, **lookup).first())
    if t is None:
        return None
    t.status = status
    t.decided_by = by if by.is_authenticated else None
    t.decided_at = timezone.now()
    t.save(update_fields=['status', 'decided_by', 'decided_at'])
    return t


def accept(transfer_id, school, *, by):
    """Хүлээн авагч сургууль зөвшөөрч, сурагчийг шилжүүлнэ."""
    with transaction.atomic():
        t = _decide(transfer_id, school, Status.ACCEPTED, by)
        if t is None:
            return None
        enrollment.enroll(t.user, t.to_school, by=by, note=f'шилжүүлэг #{t.pk}')
        # UserMeta.school өөр сургууль байсан бол enroll эх сургуулийн бүлгээс хасахгүй.
        if t.from_school.group_id:
            t.from_school.group.user_set.remove(t.user)
        return t


def reject(transfer_id, school, *, by):
    with transaction.atomic():
        return _decide(transfer_id, school, Status.REJECTED, by)


def cancel(transfer_id, school, *, by):
    """Илгээгч сургууль хүсэлтээ буцаана."""
    with transaction.atomic():
        return _decide(transfer_id, school, Status.CANCELLED, by)


# --- Имэйл мэдэгдэл ---

def _recipients(*users):
    from .moderator import blocked_emails

    blocked = blocked_emails()
    emails = []
    for u in users:
        e = (getattr(u, 'email', '') or '').strip()
        if e and e.lower() not in blocked and e.lower() not in {x.lower() for x in emails}:
            emails.append(e)
    return emails


def _send(subject, body, to):
    if not to:
        return False
    try:
        text_email(subject, body, settings.DEFAULT_FROM_EMAIL, to).send()
        return True
    except Exception:
        logger.exception('Шилжүүлгийн мэдэгдэл илгээж чадсангүй: %s', subject)
        return False


def _names(transfers):
    return '\n'.join(f'  - {t.user.last_name} {t.user.first_name} ({t.user.username})' for t in transfers)


def notify_requested(created, from_school, to_school, link):
    """Хүлээн авагч сургуулийн бүртгэгч багш, менежерт мэдэгдэнэ."""
    to = _recipients(to_school.user, to_school.manager)
    body = (
        'Сайн байна уу,\n\n'
        f'{from_school.name} ({from_school.province.name if from_school.province else ""}) сургууль '
        f'{len(created)} сурагчийг танай {to_school.name} сургууль руу шилжүүлэх хүсэлт илгээлээ:\n\n'
        f'{_names(created)}\n\n'
        'Доорх холбоосоор орж хүлээн авах эсвэл татгалзана уу. Хүлээн авах хүртэл сурагчид хуучин '
        'сургуульдаа бүртгэлтэй хэвээр байна.\n\n'
        f'{link}\n\n'
        'Монголын Математикийн Олимпиадын Хороо\n'
        'registration@mmo.mn'
    )
    return _send(f'mmo.mn: {from_school.name} сургуулиас {len(created)} сурагч шилжүүлэх хүсэлт', body, to)


def notify_decided(transfers, to_school, accepted):
    """Хүсэлт илгээсэн хүн бүрт шийдвэрийг мэдэгдэнэ."""
    by_requester = {}
    for t in transfers:
        if t.requested_by_id:
            by_requester.setdefault(t.requested_by, []).append(t)
    word = 'хүлээн авлаа' if accepted else 'татгалзлаа'
    for requester, items in by_requester.items():
        body = (
            f'Сайн байна уу, {requester.first_name},\n\n'
            f'{to_school.name} сургууль таны шилжүүлэх хүсэлт гаргасан {len(items)} сурагчийг {word}:\n\n'
            f'{_names(items)}\n\n'
            + ('Эдгээр сурагч одоо шинэ сургуулийн жагсаалтад орсон.\n\n' if accepted else
               'Эдгээр сурагч танай сургуульд бүртгэлтэй хэвээр байна.\n\n')
            + 'Монголын Математикийн Олимпиадын Хороо\nregistration@mmo.mn'
        )
        _send(f'mmo.mn: шилжүүлгийн хүсэлтийг {to_school.name} {word}', body, _recipients(requester))
