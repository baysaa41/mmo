from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from schools.models import School


def load_schools(request):
    province_id = request.GET.get('province_id')
    # province_id-г ашиглан зөвхөн тухайн аймагт хамаарах сургуулиудыг шүүх
    schools = School.objects.filter(province_id=province_id).order_by('name')
    # Сургуулиудын ID болон нэрийг JSON хэлбэрээр буцаах
    return JsonResponse(list(schools.values('id', 'name')), safe=False)


@login_required
def lookup_user(request):
    """Хэрэглэгчийн мэдээллийг ID-гаар хайж буцаана (staff only)."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Зөвшөөрөлгүй.'}, status=403)
    user_id = request.GET.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'user_id шаардлагатай.'}, status=400)
    try:
        user = User.objects.select_related('data__school', 'data__province', 'data__grade').get(id=int(user_id))
    except (User.DoesNotExist, ValueError):
        return JsonResponse({'error': f'ID {user_id} хэрэглэгч олдсонгүй.'}, status=404)
    data = getattr(user, 'data', None)
    return JsonResponse({
        'id': user.id,
        'username': user.username,
        'last_name': user.last_name,
        'first_name': user.first_name,
        'school': data.school.name if data and data.school else '',
        'province': data.province.name if data and data.province else '',
        'grade': data.grade.name if data and data.grade else '',
    })


def _apply_field_search(queryset, query):
    """Таслалаар зааглагдсан key=value хайлт (AND логик)."""
    FIELD_MAP = {
        'id': 'id',
        'username': 'username__icontains',
        'овог': 'last_name__icontains',
        'нэр': 'first_name__icontains',
        'сургууль': 'data__school__name__icontains',
        'аймаг': 'data__province__name__icontains',
        'регистр': 'data__reg_num__icontains',
        'утас': 'data__mobile__icontains',
        'имэйл': 'email__icontains',
    }
    parts = [p.strip() for p in query.split(',') if '=' in p]
    for part in parts:
        key, _, value = part.partition('=')
        key = key.strip().lower()
        value = value.strip()
        if not value:
            continue
        lookup = FIELD_MAP.get(key)
        if not lookup:
            continue
        if lookup == 'id':
            try:
                queryset = queryset.filter(id=int(value))
            except ValueError:
                queryset = queryset.none()
        else:
            queryset = queryset.filter(**{lookup: value})
    return queryset


@login_required
def search_users(request):
    """AJAX хэрэглэгч хайх (staff only). Нэгтгэх хэрэглэгч хайхад ашиглана."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Зөвшөөрөлгүй.'}, status=403)
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse({'results': []})

    users_query = User.objects.filter(
        is_active=True
    ).exclude(
        Q(last_name='') | Q(last_name__isnull=True) |
        Q(first_name='') | Q(first_name__isnull=True)
    ).select_related(
        'data__province', 'data__school', 'data__grade'
    )

    if '=' in query:
        # key=value форматтай AND хайлт (Нэр=Хулан, Овог=Бат гэх мэт)
        users_query = _apply_field_search(users_query, query)
    else:
        try:
            query_int = int(query)
            q_filter = (
                Q(last_name__icontains=query) |
                Q(first_name__icontains=query) |
                Q(id=query_int) |
                Q(data__reg_num__icontains=query) |
                Q(data__mobile__icontains=query) |
                Q(email__icontains=query)
            )
        except ValueError:
            q_filter = (
                Q(last_name__icontains=query) |
                Q(first_name__icontains=query) |
                Q(data__reg_num__icontains=query) |
                Q(data__mobile__icontains=query) |
                Q(email__icontains=query)
            )
        users_query = users_query.filter(q_filter)

    results = users_query.order_by('last_name', 'first_name')[:20]

    data = []
    for user in results:
        um = getattr(user, 'data', None)
        data.append({
            'id': user.id,
            'last_name': user.last_name,
            'first_name': user.first_name,
            'province': um.province.name if um and um.province else '',
            'school': um.school.name if um and um.school else '',
            'grade': um.grade.name if um and um.grade else '',
            'reg_num': um.reg_num if um else '',
        })

    return JsonResponse({'results': data})
