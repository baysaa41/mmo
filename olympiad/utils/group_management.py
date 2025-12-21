"""
Олимпиадын бүлэг удирдах utility функцүүд
"""
from django.contrib.auth.models import Group


def ensure_olympiad_has_group(olympiad, group_name_template=None):
    """
    Олимпиадад бүлэг байгаа эсэхийг шалгаад, байхгүй бол үүсгэнэ.

    Args:
        olympiad: Olympiad object
        group_name_template: str, бүлгийн нэрийн загвар (option)
                             None бол: "Round2_Olympiad_{olympiad.id}"

    Returns:
        tuple (group, created): Group object and boolean indicating if created
    """
    # Олимпиадад аль хэдийн бүлэг байвал түүнийг буцаана
    if olympiad.group:
        return olympiad.group, False

    # Бүлгийн нэр үүсгэх
    if group_name_template:
        group_name = group_name_template.format(olympiad=olympiad)
    else:
        group_name = f"Round2_Olympiad_{olympiad.id}"

    # Бүлэг үүсгэх эсвэл авах
    group, created = Group.objects.get_or_create(name=group_name)

    # Олимпиадад холбох
    olympiad.group = group
    olympiad.save(update_fields=['group'])

    return group, created


def get_or_create_round2_group(olympiad, province_id=None):
    """
    Round 2 олимпиадын бүлэг авах эсвэл үүсгэх.

    Хэрэв province_id өгөгдвөл: Round2_{province_id}_{olympiad.id}
    Үгүй бол: Round2_Olympiad_{olympiad.id}

    Args:
        olympiad: Olympiad object (round=2)
        province_id: int, аймгийн ID (optional)

    Returns:
        tuple (group, created): Group object and boolean
    """
    # Олимпиадад бүлэг байвал түүнийг ашиглах
    if olympiad.group:
        return olympiad.group, False

    # Бүлгийн нэр үүсгэх
    if province_id:
        group_name = f"Round2_{province_id}_{olympiad.id}"
    else:
        group_name = f"Round2_Olympiad_{olympiad.id}"

    # Бүлэг үүсгэх эсвэл авах
    group, created = Group.objects.get_or_create(name=group_name)

    # Олимпиадад холбох
    olympiad.group = group
    olympiad.save(update_fields=['group'])

    return group, created


def add_user_to_olympiad_group(user, olympiad):
    """
    Хэрэглэгчийг олимпиадын бүлэгт нэмнэ.
    Олимпиадад бүлэг байхгүй бол үүсгэнэ.

    Args:
        user: User object
        olympiad: Olympiad object

    Returns:
        bool: True if user was added, False if already in group
    """
    # Олимпиадад бүлэг байгаа эсэхийг шалгах
    group, created = ensure_olympiad_has_group(olympiad)

    # Хэрэглэгч аль хэдийн группт байгаа эсэхийг шалгах
    if group.user_set.filter(id=user.id).exists():
        return False

    # Группт нэмэх
    group.user_set.add(user)
    return True


def remove_user_from_olympiad_group(user, olympiad):
    """
    Хэрэглэгчийг олимпиадын бүлгээс хасна.

    Args:
        user: User object
        olympiad: Olympiad object

    Returns:
        bool: True if user was removed, False if not in group
    """
    if not olympiad.group:
        return False

    if not olympiad.group.user_set.filter(id=user.id).exists():
        return False

    olympiad.group.user_set.remove(user)
    return True


def get_olympiad_participants(olympiad):
    """
    Олимпиадын бүлгийн бүх гишүүдийг буцаана.

    Args:
        olympiad: Olympiad object

    Returns:
        QuerySet of User objects (эсвэл empty QuerySet)
    """
    from django.contrib.auth.models import User

    if not olympiad.group:
        return User.objects.none()

    return olympiad.group.user_set.all()
