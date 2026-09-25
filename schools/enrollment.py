"""
Сурагчийн сургуулийн гишүүнчлэлийг удирдах цорын ганц service.

Сурагчийн сургууль хоёр газар хадгалагддаг:
  - UserMeta.school  (сурагч аль сургуулийг сонгосон/оноогдсон)
  - School.group     (сургууль батлан бүртгэсэн эсэх)
Эдгээрийг зөрүүлэхгүйн тулд group-т нэмэх/хасах, UserMeta.school солих
үйлдлийг зөвхөн энэ модулийн функцээр, нэг транзакцид хийнэ. Өөрчлөлт бүр
EnrollmentLog-д бичигдэнэ.
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Exists, OuterRef, Q

from accounts.models import UserMeta
from .models import EnrollmentLog

Action = EnrollmentLog.Action


def _log(user, action, *, from_school=None, to_school=None, by=None, note=''):
    return EnrollmentLog.objects.create(
        user=user, action=action, from_school=from_school, to_school=to_school,
        performed_by=by if by is not None and by.is_authenticated else None,
        note=note[:255],
    )


def _is_member(user, school):
    return bool(school and school.group_id) and user.groups.filter(pk=school.group_id).exists()


def _save_meta(meta, fields=None):
    # UserMeta.save()-ийн хуучин группээс хасах hook-ийг давхар ажиллуулахгүй.
    meta._enrollment_handled = True
    try:
        meta.save(update_fields=fields) if fields else meta.save()
    finally:
        meta._enrollment_handled = False


def enroll(user, school, *, by=None, level=None, note=''):
    """
    Сурагчийг сургуульд бүртгэнэ: UserMeta.school/province (+level)-ийг
    оноож, сургуулийн группт нэмнэ. Өөр сургуулийн группт байсан бол тэндээс
    хасна (шилжүүлэг). Log-ийн action-ийг буцаана (өөрчлөлтгүй бол None).
    """
    with transaction.atomic():
        meta, _ = UserMeta.objects.select_for_update().get_or_create(user=user)
        old_school = meta.school
        was_member = _is_member(user, school)

        if old_school and old_school != school and old_school.group_id:
            old_school.group.user_set.remove(user)

        meta.school = school
        if school.province_id:
            meta.province_id = school.province_id
        if level is not None:
            meta.level = level
        _save_meta(meta)
        user.data = meta  # дуудагчийн user.data cache хуучин сургуультай үлдэхгүй

        if school.group_id:
            school.group.user_set.add(user)

        if old_school and old_school != school:
            action = Action.TRANSFER
        elif was_member:
            return None
        else:
            action = Action.ENROLL
        _log(user, action, from_school=old_school if old_school != school else None,
             to_school=school, by=by, note=note)
        return action


def approve(user, school, *, by=None, note=''):
    """Сургуулиа өөрөө сонгосон сурагчийг батлан бүртгэнэ. Сонгоогүй бол False."""
    meta = getattr(user, 'data', None)
    if meta is None or meta.school_id != school.pk:
        return False
    enroll(user, school, by=by, note=note or 'approve')
    return True


def unenroll(user, school, *, by=None, note=''):
    """
    Сурагчийг сургуулиас хасна. UserMeta.school нь энэ сургууль байсан бол
    цэвэрлэнэ (эс бөгөөс хасагдсан сурагч дахин "хүлээгдэж буй"-д харагдана).
    """
    with transaction.atomic():
        was_member = _is_member(user, school)
        if school.group_id:
            school.group.user_set.remove(user)

        meta = UserMeta.objects.select_for_update().filter(user=user).first()
        if meta and meta.school_id == school.pk:
            meta.school = None
            _save_meta(meta, fields=['school'])
            user.data = meta
        elif not was_member:
            return False

        _log(user, Action.UNENROLL, from_school=school, by=by, note=note)
        return True


def leave_old_school_group(user, old_school, *, new_school=None):
    """
    UserMeta.save() service-ээс гадуур сургууль солиход (профайл засах,
    management команд г.м.) дуудагдана: хуучин группээс хасаж log үлдээнэ.
    """
    if not _is_member(user, old_school):
        return False
    old_school.group.user_set.remove(user)
    _log(user, Action.UNENROLL, from_school=old_school, to_school=new_school,
         note='UserMeta.save: сургууль солигдсон')
    return True


def record_school_request(user, old_school, new_school, *, by=None, note=''):
    """
    Сурагч (эсвэл staff) профайл дээр сургууль сонгосныг бүртгэнэ. Хуучин
    группээс хасалтыг UserMeta.save() хийдэг; энд зөвхөн log үлдээнэ.
    """
    if old_school == new_school or new_school is None:
        return None
    return _log(user, Action.REQUEST, from_school=old_school, to_school=new_school, by=by, note=note)


def current_school_year_start():
    from olympiad.models import SchoolYear

    today = date.today()
    school_year = SchoolYear.objects.filter(start__lte=today, end__gte=today).first()
    return school_year.start if school_year else today - timedelta(days=365)


def pending_students(school):
    """
    Сургуулиа сонгосон боловч батлагдаагүй сурагчид.

    Зөвхөн энэ хичээлийн жилд сургуулиа сонгосон (REQUEST log) эсвэл
    нэвтэрсэн сурагчдыг тооцно. Өмнөх жилүүдийн, ялангуяа сургуулийн нэрийг
    таамаглаж оноосон (fill_school_prediction) идэвхгүй бүртгэлүүд модераторын
    жагсаалтыг дүүргэж, "бүгдийг батлах"-аар буруу сургуульд орохоос сэргийлнэ.
    """
    since = current_school_year_start()
    recent_request = EnrollmentLog.objects.filter(
        user=OuterRef('pk'), action=Action.REQUEST, to_school=school, created_at__date__gte=since,
    )
    qs = User.objects.filter(data__school=school).filter(
        Q(last_login__date__gte=since) | Exists(recent_request)
    )
    if school.group_id:
        qs = qs.exclude(groups=school.group_id)
    return qs

