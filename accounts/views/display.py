# accounts/views/display.py
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib.auth.models import Group, User
from django.contrib import messages
from django.db.models import Q
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.conf import settings
from ..models import Province, Level, UserMeta, Zone, UserMergeRequest
from schools.models import School
from .. import services
import datetime


def _send_confirmation_emails(merge_request, users):
    """
    Нэгтгэх хүсэлтийн баталгаажуулах имэйл илгээх
    """
    from django.contrib.sites.shortcuts import get_current_site
    from django.http import HttpRequest

    # Create a fake request to get domain
    fake_request = HttpRequest()
    fake_request.META['SERVER_NAME'] = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost'
    fake_request.META['SERVER_PORT'] = '80'

    for user in users:
        if not user.email:
            continue

        user_id_str = str(user.id)
        token = merge_request.confirmations.get(user_id_str, {}).get('token')

        if not token:
            continue

        # Build confirmation URLs
        confirm_url = f"{settings.SITE_URL}{reverse('merge_request_user_confirm', kwargs={'pk': merge_request.id, 'user_id': user.id, 'token': token})}"
        reject_url = f"{settings.SITE_URL}{reverse('merge_request_user_decline', kwargs={'pk': merge_request.id, 'user_id': user.id, 'token': token})}"

        # Render email template
        html_message = render_to_string('accounts/emails/merge_confirmation_request.html', {
            'user': user,
            'users': users,
            'merge_request': merge_request,
            'confirm_url': confirm_url,
            'reject_url': reject_url,
            'current_year': datetime.datetime.now().year,
        })

        # Send email
        try:
            send_mail(
                subject=f'[MMO] Нэгтгэх хүсэлт #{merge_request.id} - Баталгаажуулна уу',
                message=f'Нэгтгэх хүсэлт #{merge_request.id}\n\nБаталгаажуулах: {confirm_url}\nТатгалзах: {reject_url}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=True,
            )
        except Exception as e:
            # Log error but don't fail the request creation
            print(f"Failed to send email to {user.email}: {e}")


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
    users = group.user_set.all().order_by('data__province', 'data__school__name', 'first_name', 'last_name')

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


def _apply_field_search(queryset, query, is_staff=False):
    """
    Таслалаар зааглагдсан key=value хайлт (AND логик).
    Жишээ: id=123, Овог=Бат, Нэр=Дорж
    """
    FIELD_MAP = {
        'id': 'id',
        'username': 'username__icontains',
        'овог': 'last_name__icontains',
        'нэр': 'first_name__icontains',
        'сургууль': 'data__school__name__icontains',
        'аймаг': 'data__province__name__icontains',
    }
    STAFF_FIELD_MAP = {
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
        lookup = FIELD_MAP.get(key) or (STAFF_FIELD_MAP.get(key) if is_staff else None)
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
def participant_search(request):
    """
    Оролцогчдыг хайх хуудас (нэвтэрсэн хэрэглэгч бүрт нээлттэй)
    """
    # Get search parameters
    query = request.GET.get('q', '').strip()
    province_id = request.GET.get('p', '')
    zone_id = request.GET.get('z', '')
    school_id = request.GET.get('s', '')

    # Check if any search parameter is provided
    has_search_params = bool(query or province_id or zone_id or school_id)

    # Base queryset - exclude users without last_name or first_name
    if has_search_params:
        users_query = User.objects.filter(
            is_active=True
        ).exclude(
            Q(last_name='') | Q(last_name__isnull=True) |
            Q(first_name='') | Q(first_name__isnull=True)
        ).select_related(
            'data__province',
            'data__school',
            'data__grade',
            'data__level'
        )
    else:
        # No search parameters - return empty queryset
        users_query = User.objects.none()

    # Apply search filters
    is_staff = request.user.is_staff
    if query:
        # key=value форматтай AND хайлт шалгах
        if '=' in query:
            users_query = _apply_field_search(users_query, query, is_staff=is_staff)
        else:
            # Энгийн хайлт: OR логик
            try:
                query_int = int(query)
                q_filter = (
                    Q(last_name__icontains=query) |
                    Q(first_name__icontains=query) |
                    Q(id=query_int)
                )
            except ValueError:
                q_filter = (
                    Q(last_name__icontains=query) |
                    Q(first_name__icontains=query)
                )
            if is_staff:
                q_filter = q_filter | Q(data__reg_num__icontains=query) | Q(data__mobile__icontains=query) | Q(email__icontains=query)
            users_query = users_query.filter(q_filter)

    # Filter by province
    if province_id:
        users_query = users_query.filter(data__province_id=province_id)

    # Filter by zone
    if zone_id:
        users_query = users_query.filter(data__province__zone_id=zone_id)

    # Filter by school
    if school_id:
        users_query = users_query.filter(data__school_id=school_id)

    # Pagination
    paginator = Paginator(users_query.order_by('last_name', 'first_name'), 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get filter options
    provinces = Province.objects.all().order_by('name')
    zones = Zone.objects.all().order_by('name')

    # Get schools filtered by province if selected
    schools = School.objects.all().order_by('name')
    if province_id:
        schools = schools.filter(province_id=province_id)

    context = {
        'users': page_obj,
        'provinces': provinces,
        'zones': zones,
        'schools': schools,
        'search_query': query,
        'selected_province': province_id,
        'selected_zone': zone_id,
        'selected_school': school_id,
    }

    return render(request, 'accounts/participant_search.html', context)


def merge_request_confirm(request, pk, user_id, token):
    """
    Хэрэглэгч нэгтгэх хүсэлтийг баталгаажуулах (GET линк)
    """
    merge_request = get_object_or_404(UserMergeRequest, pk=pk)

    success, message = merge_request.confirm_by_user(user_id, token)

    if success:
        messages.success(request, message)
        # Check if auto-merged
        if merge_request.status == UserMergeRequest.Status.COMPLETED:
            messages.success(
                request,
                "Бүх хэрэглэгч баталгаажуулсан тул автоматаар нэгтгэгдлээ!"
            )
    else:
        messages.error(request, message)

    return render(request, 'accounts/merge_confirmation_result.html', {
        'merge_request': merge_request,
        'success': success,
        'message': message,
    })


def merge_request_reject(request, pk, user_id, token):
    """
    Хэрэглэгч нэгтгэх хүсэлтийг татгалзах (GET линк)
    """
    merge_request = get_object_or_404(UserMergeRequest, pk=pk)

    success, message = merge_request.reject_by_user(user_id, token)

    if success:
        messages.warning(request, message)
    else:
        messages.error(request, message)

    return render(request, 'accounts/merge_confirmation_result.html', {
        'merge_request': merge_request,
        'success': success,
        'message': message,
    })


@login_required
def create_merge_request(request):
    """
    Нэгтгэх хүсэлт үүсгэх (POST)
    """
    if request.method == 'POST':
        user_ids_str = request.POST.get('user_ids', '')
        reason = request.POST.get('reason', '')

        # Parse user IDs
        try:
            user_ids = [int(uid.strip()) for uid in user_ids_str.split(',') if uid.strip()]
        except ValueError:
            messages.error(request, "Буруу хэрэглэгчийн ID байна.")
            return redirect('participant_search')

        if len(user_ids) < 2:
            messages.error(request, "Хамгийн багадаа 2 хэрэглэгчийг сонгоно уу.")
            return redirect('participant_search')

        # Check if users exist
        users = User.objects.filter(id__in=user_ids)
        if users.count() != len(user_ids):
            missing_ids = set(user_ids) - set(users.values_list('id', flat=True))
            messages.error(
                request,
                f"Зарим хэрэглэгч олдсонгүй (ID: {', '.join(map(str, missing_ids))}). "
                f"Магадгүй өмнө нь нэгтгэгдсэн байж болзошгүй."
            )
            return redirect('participant_search')

        # Create merge request
        merge_request = UserMergeRequest.objects.create(
            requesting_user=request.user,
            user_ids=user_ids,
            reason=reason,
            status=UserMergeRequest.Status.PENDING,
            requires_user_confirmation=True
        )

        # Initialize confirmations for each user
        merge_request.initialize_confirmations()

        # Detect conflicts
        merge_request.detect_conflicts()
        merge_request.save()

        # Send confirmation emails to all affected users
        _send_confirmation_emails(merge_request, users)

        messages.success(
            request,
            f"Нэгтгэх хүсэлт #{merge_request.id} амжилттай үүслээ. "
            f"Холбогдох хэрэглэгчдэд имэйл илгээгдсэн. Бүгд баталгаажуулбал автоматаар нэгтгэгдэнэ."
        )

        return redirect('merge_request_detail', pk=merge_request.id)

    return redirect('participant_search')