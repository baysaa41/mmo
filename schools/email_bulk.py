"""
Багш (нэг имэйлд олон сурагчийн аккаунт бүртгүүлсэн хүн) сурагчдынхаа имэйлийг Excel-ээр бөөнөөр солих.

Урсгал (I давааны имэйлийн нэвтрэлтгүй холбоос `/schools/r1/<token>/`-оос):
  1. build_workbook(email)       — тухайн имэйлтэй аккаунтуудын Excel (ID, нэр, сургууль, анги, имэйл, «Шинэ имэйл»)
  2. build_plan(email, anchor, ws) — файлыг уншиж, мөр бүрийг шалгана (юу ч өөрчлөхгүй)
  3. apply_changes(...)          — багш баталгаажуулсны дараа имэйлийг сольж, шинэ хаяг руу нууц үг тохируулах
                                    холбоос илгээнэ (celery: schools.tasks.send_email_change_links_task)

Хамгаалалт: зөвхөн токены имэйлтэй аккаунтыг солино; токен үүсгэсэн (anchor) аккаунт, staff/superuser,
сургуулийн бүртгэгч/удирдлага, аймгийн админ орохгүй. Шинэ имэйл өөр идэвхтэй аккаунтад байвал татгалзана.
"""
import csv
import io
import os
import re
from collections import Counter

from django.conf import settings
from django.contrib.auth.models import User
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from accounts.models import Province
from emails.suppression import email_typo_suggestion
from . import round1_links as links
from .models import School
from .moderator import blocked_emails, norm_email

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10000
LOG_PATH = os.path.join(settings.BASE_DIR, 'logs', 'email_bulk_changes.csv')
HEADERS = ['ID', 'Овог', 'Нэр', 'Сургууль', 'Анги', 'Одоогийн имэйл', 'Шинэ имэйл']
NEW_COL = HEADERS.index('Шинэ имэйл')

OK = 'ok'
# Татгалзах шалтгаанууд (тайланд харуулна)
NOT_YOURS = 'Энэ ID таны имэйлтэй аккаунт биш (эсвэл солих боломжгүй)'
BAD_FORMAT = 'Имэйлийн формат буруу'
TYPO = 'Домэйны бичгийн алдаатай'
BLOCKED = 'Энэ хаяг руу имэйл хүрэхгүй (bounce/complaint/татгалзсан)'
SAME_AS_OLD = 'Одоогийн имэйлтэй ижил'
TAKEN = 'Өөр хүнд бүртгэлтэй имэйл'
DUP_IN_FILE = 'Файлд олон удаа давтагдсан'
BAD_ID = 'ID буруу'


def anchor_uid(token):
    """Токен үүсгэсэн аккаунтын id (round1_links.read_token-той ижил гарын үсэг)."""
    try:
        return int(signing.TimestampSigner(salt=links.SALT).unsign(token, max_age=links.MAX_AGE))
    except (signing.BadSignature, ValueError):
        return None


def editable_accounts(email, anchor):
    """Багш солих эрхтэй аккаунтууд (токены имэйлтэй, идэвхтэй, албан тушаалгүй)."""
    users = list(links.accounts_for_email(email).filter(is_staff=False, is_superuser=False))
    ids = [u.pk for u in users]
    official = set(School.objects.filter(user_id__in=ids).values_list('user_id', flat=True))
    official |= set(School.objects.filter(manager_id__in=ids).values_list('manager_id', flat=True))
    for field in ('contact_person', 'contact_person2', 'registrar'):
        official |= set(Province.objects.filter(**{field + '__in': ids}).values_list(field, flat=True))
    return [u for u in users if u.pk != anchor and u.pk not in official]


def build_workbook(email, anchor):
    """Excel файлын bytes ба мөрийн тоо."""
    users = editable_accounts(email, anchor)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Имэйл'
    ws.append(HEADERS)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill('solid', fgColor='E8EEF7')
    ws.cell(row=1, column=NEW_COL + 1).fill = PatternFill('solid', fgColor='FFF2CC')
    for u in users:
        meta = getattr(u, 'data', None)
        ws.append([u.pk, u.last_name, u.first_name,
                   meta.school.name if meta and meta.school_id else '',
                   meta.grade.name if meta and meta.grade_id else '',
                   u.email, ''])
    for i, w in enumerate((10, 18, 18, 38, 10, 34, 34), start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'A2'
    help_ws = wb.create_sheet('Заавар')
    for line in (
        'Хүн бүр өөрийн имэйл хаягаар бүртгүүлэх нь Математикийн олимпиадын хорооны бодлого.',
        '1. «Шинэ имэйл» баганад сурагч бүрийн ӨӨРИЙН имэйл хаягийг бичнэ. Солихгүй мөрийг хоосон орхино.',
        '2. ID, нэр зэрэг бусад баганыг бүү өөрчил — ID-аар танина.',
        '3. Файлаа ижил хуудсан дээрээ «Excel файл оруулах» хэсгээр буцааж оруулна.',
        '4. Систем шалгаад үр дүнг харуулна. Та «Баталгаажуулах» дарсны дараа л имэйлүүд солигдож,',
        '   сурагч бүрийн шинэ имэйл рүү нууц үгээ тохируулах холбоос явна.',
        'Нэг имэйл хаягийг зөвхөн нэг сурагчид өгнө. Өөр хүнд аль хэдийн бүртгэлтэй хаягийг татгалзана.',
    ):
        help_ws.append([line])
    help_ws.column_dimensions['A'].width = 110
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), len(users)


def _read_rows(file_obj):
    """[(row_number, id_text, new_email_text)]. Толгойг нэрээр нь хайна."""
    wb = load_workbook(file_obj, read_only=True, data_only=True)
    ws = wb['Имэйл'] if 'Имэйл' in wb.sheetnames else wb.worksheets[0]
    id_col = new_col = None
    out = []
    for n, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if id_col is None:
            cells = [str(c).strip().lower() if c is not None else '' for c in row]
            if 'id' in cells and 'шинэ имэйл' in cells:
                id_col, new_col = cells.index('id'), cells.index('шинэ имэйл')
            elif n >= 10:
                break
            continue
        if len(out) >= MAX_ROWS:
            raise ValueError(f'Мөрийн тоо {MAX_ROWS}-аас хэтэрсэн.')
        raw_id = row[id_col] if id_col < len(row) else None
        raw_new = row[new_col] if new_col < len(row) else None
        if raw_id in (None, '') and raw_new in (None, ''):
            continue
        out.append((n, raw_id, raw_new))
    if id_col is None:
        raise ValueError('Толгой мөр олдсонгүй: «ID» ба «Шинэ имэйл» баганатай татсан файлаа ашиглана уу.')
    return out


def _clean_id(raw):
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    text = str(raw).strip()
    return int(text) if text.isdigit() else None


def validate_row(user, new_email, blocked, taken, seen_counts):
    """(норм. имэйл, None) эсвэл (None, шалтгаан)."""
    raw = (new_email or '').strip()
    try:
        validate_email(raw)
    except ValidationError:
        return None, BAD_FORMAT
    new = norm_email(raw)
    if not new:
        return None, BAD_FORMAT
    if email_typo_suggestion(new):
        return None, TYPO
    if new == norm_email(user.email):
        return None, SAME_AS_OLD
    if new in blocked:
        return None, BLOCKED
    if seen_counts[new] > 1:
        return None, DUP_IN_FILE
    if new in taken:
        return None, TAKEN
    return new, None


def _taken_emails(candidates, exclude_ids):
    """Дараах хаягуудаас өөр идэвхтэй аккаунтад бүртгэлтэйг нь (lower)."""
    from django.db.models.functions import Lower
    found = set()
    cands = list(candidates)
    for i in range(0, len(cands), 1000):
        qs = (User.objects.annotate(le=Lower('email')).filter(le__in=cands[i:i + 1000])
              .exclude(pk__in=exclude_ids).values_list('le', flat=True))
        found |= set(qs)
    return found


def build_plan(email, anchor, file_obj):
    """Файлыг шалгаж төлөвлөгөө гаргана — юу ч өөрчлөхгүй.

    Буцаах: {'changes': [(uid, old, new, label)], 'rejected': [(row, label, new_text, reason)],
             'unchanged': int, 'reasons': Counter}
    """
    rows = _read_rows(file_obj)
    users = {u.pk: u for u in editable_accounts(email, anchor)}
    blocked = blocked_emails()
    wanted = []
    for _n, raw_id, raw_new in rows:
        if raw_new not in (None, '') and str(raw_new).strip():
            wanted.append(norm_email(str(raw_new)))
    seen = Counter(e for e in wanted if e)
    taken = _taken_emails({e for e in seen}, exclude_ids=list(users))
    changes, rejected, unchanged = [], [], 0
    for n, raw_id, raw_new in rows:
        text = '' if raw_new is None else str(raw_new).strip()
        uid = _clean_id(raw_id)
        if not text:
            unchanged += 1
            continue
        if uid is None:
            rejected.append((n, str(raw_id), text, BAD_ID))
            continue
        user = users.get(uid)
        if user is None:
            rejected.append((n, str(uid), text, NOT_YOURS))
            continue
        label = f'{user.last_name} {user.first_name}'.strip() or user.username
        new, reason = validate_row(user, text, blocked, taken, seen)
        if reason:
            rejected.append((n, f'{uid} · {label}', text, reason))
        else:
            changes.append((uid, user.email, new, label))
    return {'changes': changes, 'rejected': rejected, 'unchanged': unchanged,
            'reasons': Counter(r[3] for r in rejected)}


def apply_changes(email, anchor, pairs):
    """pairs: [(uid, new_email)]. Баталгаажуулах үед дахин шалгаад солино.

    Буцаах: (солигдсон uid-ууд, татгалзсан [(uid, шалтгаан)]).
    """
    users = {u.pk: u for u in editable_accounts(email, anchor)}
    blocked = blocked_emails()
    seen = Counter(norm_email(n) for _, n in pairs)
    taken = _taken_emails(set(seen), exclude_ids=list(users))
    done, rejected, log_rows = [], [], []
    now = timezone.now().isoformat(timespec='seconds')
    with transaction.atomic():
        for uid, new_text in pairs:
            user = users.get(uid)
            if user is None:
                rejected.append((uid, NOT_YOURS))
                continue
            new, reason = validate_row(user, new_text, blocked, taken, seen)
            if reason:
                rejected.append((uid, reason))
                continue
            log_rows.append([now, anchor, uid, user.username, user.email, new])
            user.email = new
            user.save(update_fields=['email'])
            done.append(uid)
    _append_log(log_rows)
    return done, rejected


def _append_log(rows):
    if not rows:
        return
    new_file = not os.path.exists(LOG_PATH)
    with open(LOG_PATH, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(['at', 'anchor_uid', 'user_id', 'username', 'old_email', 'new_email'])
        w.writerows(rows)


def send_set_password_links(user_ids):
    """Шинэ имэйл бүр рүү нууц үг тохируулах холбоос. (илгээсэн, алгассан) тоо."""
    import time
    from django.contrib.auth.tokens import default_token_generator
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode
    from emails.html import text_to_html
    from .moderator import NOTICE_FROM_EMAIL

    blocked = blocked_emails()
    site = settings.SITE_URL.rstrip('/')
    sent = skipped = 0
    for user in User.objects.filter(pk__in=user_ids, is_active=True):
        if not norm_email(user.email) or norm_email(user.email) in blocked:
            skipped += 1
            continue
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        body = render_to_string('schools/emails/email_changed_set_password.txt', {
            'user': user, 'reset_url': f'{site}/accounts/password-reset/{uid}/{token}/',
            'from_email': NOTICE_FROM_EMAIL,
        })
        msg = EmailMultiAlternatives('ММО-63: имэйл хаяг шинэчлэгдлээ — нууц үгээ тохируулна уу',
                                     body, NOTICE_FROM_EMAIL, [user.email])
        msg.attach_alternative(text_to_html(body), 'text/html')
        msg.send()
        sent += 1
        time.sleep(0.1)  # SES-ийн секундэд илгээх хязгаарт багтаана
    return sent, skipped
