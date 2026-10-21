"""
I давааны имэйлийн нэвтрэлтгүй хувийн холбоос (signed token).

Нэг имэйл хаяг руу нэг л имэйл очдог тул холбоос нь тухайн хаягтай БҮХ идэвхтэй аккаунтын
хуудсыг нээнэ. Токенд тухайн хаягтай хамгийн жижиг id-тай аккаунтын id-г гарын үсэгтэй
хийнэ (URL-д имэйл ил гарахгүй); хаягийг нээх үед тэр аккаунтын одоогийн имэйлээр олно.

Үйлдлүүд (бүгд POST — имэйлийн аюулгүй байдлын сканнер GET холбоосыг урьдчилан нээдэг):
  - request:   сургуулиа сонгосон боловч бүртгэлгүй аккаунтыг бүртгэгч багшид хүсэлт болгох
               (EnrollmentLog.REQUEST → багшийн «хүлээгдэж буй» жагсаалтад гарна, өдөр бүрийн
               нэгдсэн имэйлээр мэдэгдэнэ)
  - interests: ММО / бусад олимпиад / MathMinds мэдээлэл авах сонирхол
  - unsubscribe
"""
from django.contrib.auth.models import User
from django.core import signing
from django.db import transaction
from django.utils import timezone

from accounts.models import UserMeta
from .enrollment import current_school_year_start
from .models import EnrollmentLog
from .moderator import norm_email

SALT = 'schools.round1_links'
MAX_AGE = 120 * 24 * 3600  # 4 сар — I, II даваа дуустал хүчинтэй
REQUEST_NOTE = 'round1-email'
INTERESTS = ('wants_mmo_news', 'wants_other_olympiads', 'wants_mathminds')

# account_status()-ийн утгууд
REGISTERED = 'registered'
REQUESTED = 'requested'
NOT_REGISTERED = 'not_registered'
NO_SCHOOL = 'no_school'


def make_token(email):
    """Тухайн хаягийн токен. Хаягтай идэвхтэй аккаунт байхгүй бол None."""
    uid = (User.objects.filter(email__iexact=email, is_active=True)
           .order_by('id').values_list('id', flat=True).first())
    return token_for_uid(uid) if uid else None


def token_for_uid(uid):
    """make_token-той ижил; бөөнөөр илгээхэд хаягийн хамгийн жижиг id-г өөрөө өгнө."""
    return signing.TimestampSigner(salt=SALT).sign(str(uid))


def read_token(token):
    """Токеноос имэйл хаяг. Буруу/хугацаа дууссан бол None."""
    try:
        uid = int(signing.TimestampSigner(salt=SALT).unsign(token, max_age=MAX_AGE))
    except (signing.BadSignature, ValueError):
        return None
    email = User.objects.filter(pk=uid, is_active=True).values_list('email', flat=True).first()
    return norm_email(email) or None


def accounts_for_email(email):
    return (User.objects.filter(email__iexact=email, is_active=True)
            .select_related('data__school__user', 'data__school__province', 'data__grade')
            .order_by('last_name', 'first_name', 'id'))


def _requested_user_ids(users):
    """Энэ хичээлийн жилд одоогийн сургуульдаа хүсэлт илгээсэн аккаунтууд."""
    pairs = {(u.pk, u.data.school_id) for u in users if hasattr(u, 'data') and u.data.school_id}
    if not pairs:
        return set()
    logs = EnrollmentLog.objects.filter(
        user_id__in={uid for uid, _ in pairs}, action=EnrollmentLog.Action.REQUEST,
        created_at__date__gte=current_school_year_start(),
    ).values_list('user_id', 'to_school_id')
    return {uid for uid, sid in logs if (uid, sid) in pairs}


def account_rows(users):
    """[(user, status)] — хуудас болон имэйлд харуулах."""
    users = list(users)
    requested = _requested_user_ids(users)
    # meta.is_school_registered()-тэй ижил, гэхдээ олон аккаунтад нэг query-ээр
    memberships = set(User.groups.through.objects.filter(
        user_id__in=[u.pk for u in users]).values_list('user_id', 'group_id'))
    rows = []
    for u in users:
        meta = getattr(u, 'data', None)
        if meta is None or not meta.school_id:
            status = NO_SCHOOL
        elif meta.school.group_id and (u.pk, meta.school.group_id) in memberships:
            status = REGISTERED
        elif u.pk in requested:
            status = REQUESTED
        else:
            status = NOT_REGISTERED
        rows.append((u, status))
    return rows


def send_requests(email, user_ids=None):
    """Бүртгэлгүй аккаунтуудыг сургуулийн бүртгэгч багшид хүсэлт болгоно. Илгээсэн тоог буцаана."""
    users = accounts_for_email(email)
    if user_ids is not None:
        users = users.filter(pk__in=user_ids)
    created = 0
    with transaction.atomic():
        for u, status in account_rows(users):
            if status == NOT_REGISTERED:
                EnrollmentLog.objects.create(user=u, action=EnrollmentLog.Action.REQUEST,
                                             to_school=u.data.school, note=REQUEST_NOTE)
                created += 1
    return created


def current_interests(users):
    """Хаягийн аккаунтуудын сонирхол — аль нэг аккаунт дээр тэмдэглэсэн утгыг авна."""
    result = dict.fromkeys(INTERESTS)
    for u in users:
        meta = getattr(u, 'data', None)
        for f in INTERESTS:
            if meta is not None and getattr(meta, f) is not None and result[f] is None:
                result[f] = getattr(meta, f)
    return result


def interests_answered(users):
    """Хаягийн аль нэг аккаунт сонирхлоо хадгалсан эсэх (null биш = асуусан, хариулсан)."""
    return any(getattr(getattr(u, 'data', None), 'interests_updated_at', None) for u in users)


def promo_emails(field):
    """Сурталчилгаа/зар илгээж болох хаягууд: `field` (INTERESTS-ийн нэг) дээр «тийм» гэж хариулсан,
    unsubscribe хийгээгүй, идэвхтэй аккаунттай. Шинэ зар илгээхдээ зөвхөн эндээс авна."""
    from emails.models import EmailUnsubscribe
    if field not in INTERESTS:
        raise ValueError(field)
    emails = {norm_email(e) for e in User.objects.filter(
        is_active=True, **{f'data__{field}': True}).exclude(email='').values_list('email', flat=True)}
    unsub = {norm_email(e) for e in EmailUnsubscribe.objects.values_list('email', flat=True)}
    return emails - unsub - {''}


def set_interests(email, values):
    """values: {талбар: bool}. Тухайн хаягтай бүх аккаунтад хадгална."""
    fields = {f: bool(values.get(f)) for f in INTERESTS}
    return UserMeta.objects.filter(user__in=accounts_for_email(email)).update(
        **fields, interests_updated_at=timezone.now())


def unsubscribe(email, reason='I давааны имэйлийн холбоос'):
    from emails.models import EmailUnsubscribe
    users = list(accounts_for_email(email))
    for u in users:
        EmailUnsubscribe.objects.update_or_create(user=u, defaults={'email': u.email, 'reason': reason})
    return len(users)


# ----------------------------------------------------------------------------- нэгтгэх
MERGE_REASON = 'I давааны имэйлийн хувийн хуудаснаас: ижил имэйл, ижил овог нэртэй аккаунтууд нэг хүн гэж баталсан.'


def _name_key(user):
    from accounts.management.commands.automerge_users import normalize_fullname
    return normalize_fullname(user.last_name or '', user.first_name or '')


def duplicate_groups(users):
    """[[user, ...]] — нэг имэйлийн аккаунтуудаас овог нэр нь ижил (кирилл/латин нормчилсон) бүлгүүд."""
    groups = {}
    for u in users:
        if u.is_staff or u.is_superuser or not (u.first_name or u.last_name):
            continue
        groups.setdefault(_name_key(u), []).append(u)
    return [g for g in groups.values() if len(g) > 1]


def suggested_primary(group):
    """Үндсэн аккаунтын санал: сурагчийн анги (Дэмжигч биш), дүнтэй, сүүлд нэвтэрсэн нь."""
    from olympiad.models import Result, ScoreSheet

    def score(u):
        grade = getattr(getattr(getattr(u, 'data', None), 'grade', None), 'name', '') or ''
        results = Result.objects.filter(contestant=u).count() + ScoreSheet.objects.filter(user=u).count()
        return (grade not in ('', 'Дэмжигч'), results, u.last_login.timestamp() if u.last_login else 0, -u.pk)
    return max(group, key=score)


def pending_merge_ids():
    """Хүлээгдэж буй нэгтгэх хүсэлтэд орсон аккаунтын id-ууд."""
    from accounts.models import UserMergeRequest
    ids = set()
    for ids_list in UserMergeRequest.objects.filter(status=UserMergeRequest.Status.PENDING).values_list('user_ids', flat=True):
        ids |= set(ids_list)
    return ids


def request_merge(email, anchor_uid, user_ids):
    """Нэг бүлгийг админы батлах нэгтгэх хүсэлт болгоно (имэйлээр баталгаажуулалт шаардахгүй: бүгд нэг имэйл).

    Буцаах: хүсэлт, эсвэл None (бүлэг таарахгүй / аль хэдийн хүсэлттэй).
    """
    from accounts.models import UserMergeRequest
    wanted = set(user_ids)
    for group in duplicate_groups(accounts_for_email(email)):
        if {u.pk for u in group} != wanted:
            continue
        if wanted & pending_merge_ids():
            return None
        requester = User.objects.get(pk=anchor_uid)
        req = UserMergeRequest.objects.create(
            requesting_user=requester, user_ids=sorted(wanted), primary_user=suggested_primary(group),
            reason=MERGE_REASON, status=UserMergeRequest.Status.PENDING, requires_user_confirmation=False)
        req.detect_conflicts()
        req.save()
        return req
    return None
