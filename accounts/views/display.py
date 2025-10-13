# accounts/views/display.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib.auth.models import Group, User
from ..models import Province, Level, UserMeta, Zone
from .. import services

def users(request):
    try:
        province_id = int(request.GET.get('p') or 0)
        level_id = int(request.GET.get('l') or 0)
    except (ValueError, TypeError):
        province_id = level_id = 0

    if not province_id and not level_id:
        context = {'provinces': Province.objects.all(), 'levels': Level.objects.all()}
        return render(request, 'accounts/users-home.html', context)

    users_query = UserMeta.objects.filter(is_valid=1)
    title_parts = []

    if province_id:
        province = get_object_or_404(Province, pk=province_id)
        users_query = users_query.filter(province=province)
        title_parts.append(province.name)

    if level_id:
        level = get_object_or_404(Level, pk=level_id)
        users_query = users_query.filter(level=level)
        title_parts.append(level.name)

    ordering = ('grade_id', 'province_id')
    if province_id and not level_id:
        ordering = ('level_id', 'grade_id')

    user_list = users_query.order_by(*ordering)
    paginator = Paginator(user_list, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'users': page_obj,
        'title': ', '.join(title_parts)
    }
    return render(request, 'accounts/users.html', context)

def group_users(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    users = group.user_set.all().order_by('data__province__zone', 'data__province', 'data__school__name')

    # Filtering logic can also be moved to a service if it gets more complex
    # ...

    # Call the service to generate the HTML table
    html_table = services.generate_styled_user_dataframe_html(users, is_staff=request.user.is_staff)

    context = {
        'title': group.name,
        'pivot': html_table,
    }
    return render(request, 'accounts/group-users.html', context)

@staff_member_required
def staff(request):
    users = User.objects.filter(is_staff=1).order_by('data__province__zone')
    return render(request, 'accounts/staff.html', {'users': users})