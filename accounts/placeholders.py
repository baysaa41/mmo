"""
Системээс автоматаар үүсгэсэн түр («placeholder») бүртгэл — mmo-system-accounts/ТӨЛӨВЛӨГӨӨ.md.

Олимпиадын дүнг Excel-ээс оруулахад сурагч олдоогүй бол түр хэрэглэгч үүсгэдэг. Эдгээрт
≈205,000 дүн байгаа тул УСТГАХГҮЙ: бодит хэрэглэгчид нэгтгэх хүртэл хадгална.
"""
from django.db.models import Exists, OuterRef, Q

# Системийн бүртгэлийн и-мэйл → UserMeta.placeholder_source
SYSTEM_EMAILS = {
    'mmo60official@gmail.com': 'mmo60',
    'auto-user@mmo.mn': 'auto_user',
}


def placeholder_groups():
    """Тэмдэглэх бүлэг бүрийн (source, User queryset)."""
    from django.contrib.auth.models import User
    groups = [(source, User.objects.filter(email__iexact=email)) for email, source in SYSTEM_EMAILS.items()]
    # И-мэйлгүй бөгөөд хэзээ ч нэвтэрч байгаагүй (нэвтэрсэн бол бодит хэрэглэгч гэж үзнэ)
    groups.append(('no_email', User.objects.filter(Q(email='') | Q(email__isnull=True), last_login__isnull=True)))
    return [(source, qs.filter(is_staff=False, is_superuser=False)) for source, qs in groups]


def with_olympiad_data_q():
    """Олимпиадын дүн/шагнал/оноо хуудастай хэрэглэгч (User queryset-д .filter/.exclude)."""
    from olympiad.models import Award, Result, ScoreSheet
    return (Q(Exists(Result.objects.filter(contestant=OuterRef('pk'))))
            | Q(Exists(Award.objects.filter(contestant=OuterRef('pk'))))
            | Q(Exists(ScoreSheet.objects.filter(user=OuterRef('pk')))))


def protected_from_deletion_q():
    """Устгах командууд хэзээ ч хүрэх ёсгүй хэрэглэгч: placeholder эсвэл олимпиадын өгөгдөлтэй."""
    return Q(data__is_placeholder=True) | with_olympiad_data_q()
