"""
Хязгаарлагдмал эрхтэй хуудсуудад "та ямар эрхээр харж байна" гэсэн мэдэгдэл
болон мэдээллийг зөвхөн албан хэрэгцээнд ашиглах санамжийг харуулна.

    {% load access_tags %}
    {% access_notice %}

Контекстоос school, province, managed_province, zone хувьсагчдыг автоматаар уншина.
"""
from django import template

register = template.Library()


def _province_roles(user, province):
    roles = []
    if province is None:
        return roles
    if province.is_contact_person(user):
        roles.append(f'{province.name}-ийн удирдах ажилтан')
    if province.registrar_id == user.id:
        roles.append(f'{province.name}-ийн бүртгэгч багш')
    if user.groups.filter(name=f'Province_{province.id}_Managers').exists():
        roles.append(f'{province.name}-ийн менежер')
    return roles


def access_roles(user, school=None, province=None, zone=None):
    """Хэрэглэгч энэ хуудсанд ямар эрхээр хандаж байгааг жагсаана."""
    roles = []
    if user.is_superuser:
        roles.append('Админ')
    elif user.is_staff:
        roles.append('Staff')
    if school is not None:
        if school.manager_id == user.id:
            roles.append(f'{school.name}-ийн удирдлага')
        if school.user_id == user.id:
            roles.append(f'{school.name}-ийн бүртгэгч багш')
        roles += _province_roles(user, province or school.province)
    elif province is not None:
        roles += _province_roles(user, province)
    if zone is not None:
        if zone.contact_person_id == user.id:
            roles.append(f'{zone.name}-ийн удирдах ажилтан')
        if user.groups.filter(name=f'Zone_{zone.id}_Managers').exists():
            roles.append(f'{zone.name}-ийн менежер')
    return list(dict.fromkeys(roles))


@register.inclusion_tag('partials/_access_notice.html', takes_context=True)
def access_notice(context):
    request = context.get('request')
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {'roles': []}
    province = context.get('province') or context.get('managed_province')
    roles = access_roles(user, school=context.get('school'), province=province, zone=context.get('zone'))
    return {'roles': roles or ['эрх бүхий хэрэглэгч']}
