from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator
from datetime import timedelta
import os
import platform
import re
import datetime

@staff_member_required
def dashboard_view(request):
    """
    cPanel маягийн системийн мэдээлэл харуулах dashboard хуудас
    """
    User = get_user_model()

    # Import models
    from schools.models import School
    from olympiad.models import Olympiad, Result

    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    # User statistics
    total_users = User.objects.count()
    active_users_30d = User.objects.filter(last_login__gte=thirty_days_ago).count()
    active_users_7d = User.objects.filter(last_login__gte=seven_days_ago).count()
    staff_users = User.objects.filter(is_staff=True).count()
    superusers = User.objects.filter(is_superuser=True).count()
    new_users_30d = User.objects.filter(date_joined__gte=thirty_days_ago).count()
    new_users_7d = User.objects.filter(date_joined__gte=seven_days_ago).count()

    # Users by province
    users_by_province = User.objects.values('province').annotate(count=Count('id')).order_by('-count')[:10]

    # School statistics
    total_schools = School.objects.count()

    # Olympiad statistics
    total_olympiads = Olympiad.objects.count()
    total_results = Result.objects.count()

    # Recent users
    recent_users = User.objects.order_by('-date_joined')[:10]

    # System info
    system_info = {
        'platform': platform.system(),
        'python_version': platform.python_version(),
        'hostname': platform.node(),
    }

    context = {
        'total_users': total_users,
        'active_users_30d': active_users_30d,
        'active_users_7d': active_users_7d,
        'staff_users': staff_users,
        'superusers': superusers,
        'new_users_30d': new_users_30d,
        'new_users_7d': new_users_7d,
        'users_by_province': users_by_province,
        'total_schools': total_schools,
        'total_olympiads': total_olympiads,
        'total_results': total_results,
        'recent_users': recent_users,
        'system_info': system_info,
    }

    return render(request, 'accounts/dashboard.html', context)

@staff_member_required
def command_guide_view(request):
    """
    Админ хэрэглэгчдэд зориулсан, системийн тусгай коммандуудын
    тайлбар, заавар бүхий хуудсыг харуулна.
    """
    commands_data = [
        {
            'name': 'generate_answer_sheet',
            'description': 'Олимпиадын хариултыг бөглөхөд зориулсан, сурагчдын мэдээллээр урьдчилан дүүргэсэн Excel загвар файлыг үүсгэнэ. Файл нь 2 sheet-тэй, Монгол нэртэй багануудтай, хүрээтэй, цэгцтэй загвартай гарна.',
            'usage': 'python manage.py generate_answer_sheet --olympiad-id [ID] --school-id [ID] --output-file [ФАЙЛЫН ЗАМ]',
            'examples': [
                '# Хоосон загвар үүсгэх:',
                'python manage.py generate_answer_sheet --olympiad-id 55 --school-id 42 --output-file ./olymp55_school42.xlsx',
                '# Санамсаргүй хариултаар дүүргэсэн туршилтын файл үүсгэх:',
                'python manage.py generate_answer_sheet --olympiad-id 55 --school-id 42 --output-file ./test_olymp55.xlsx --test'
            ]
        },
        {
            'name': 'import_answers_from_excel',
            'description': 'Заасан хавтас доторх бүх Excel файлаас олимпиадын хариултыг уншиж, системд бөөнөөр импортолно. Импортлохын өмнө сурагчийн ID, овог нэр, сургуулийн харьяалал, хариултын формат зэргийг шалгана.',
            'usage': 'python manage.py import_answers_from_excel --directory [ХАВТАСНЫ ЗАМ]',
            'examples': [
                'python manage.py import_answers_from_excel --directory /home/deploy/answer_sheets/'
            ]
        },
        {
            'name': 'find_duplicate_users',
            'description': 'Системд давхардсан болон буруу форматтай регистрийн дугаартай хэрэглэгчдийг илрүүлж, жагсаалт харуулна. Энэ комманд мэдээллийн санд өөрчлөлт хийхгүй.',
            'usage': 'python manage.py find_duplicate_users',
            'examples': []
        },
        {
            'name': 'automerge_users',
            'description': 'Давхардсан хэрэглэгчдийг ухаалгаар нэгтгэнэ. --all горимд ажиллахдаа регистр, овог нэр таарсан хэрэглэгчдийг автоматаар, зөрсөн тохиолдолд асуулттайгаар нэгтгэнэ. Нэгтгэхээсээ өмнө дүнгийн зөрчлийг шалгадаг.',
            'usage': 'python manage.py automerge_users [--all | --reg-num [РЕГИСТР]]',
            'examples': [
                '# Бүх боломжит давхардлыг шалгах:',
                'python manage.py automerge_users --all',
                '# Зөвхөн тодорхой нэг регистрээр нэгтгэх:',
                'python manage.py automerge_users --reg-num УБ00112233'
            ]
        },
        {
            'name': 'advance_grades',
            'description': 'Хичээлийн жил дуусахад бүх сурагчдын ангийг нэгээр ахиулж, төгсөх ангийнхныг тохируулсан үүрэгт шилжүүлдэг.',
            'usage': 'python manage.py advance_grades',
            'examples': []
        },
        {
            'name': 'generate_scoresheets',
            'description': 'Олимпиадын дүн(Result)-г ашиглан нэгдсэн онооны хуудас (ScoreSheet)-г үүсгэж, улсын, аймгийн, бүсийн эрэмбийг тооцоолно.',
            'usage': 'python manage.py generate_scoresheets --olympiad-id [ID] [--force-delete]',
            'examples': [
                '# Онооны хуудас үүсгэх:',
                'python manage.py generate_scoresheets --olympiad-id 77',
                '# Хуучин оноог устгаад шинээр үүсгэх:',
                'python manage.py generate_scoresheets --olympiad-id 77 --force-delete'
            ]
        },
    ]
    context = {
        'commands': commands_data
    }
    return render(request, 'accounts/command_guide.html', context)


@staff_member_required
def merge_requests_list(request):
    """
    Бүх нэгтгэх хүсэлтүүдийн жагсаалт (Staff-д зориулсан)
    """
    from ..models import UserMergeRequest

    status_filter = request.GET.get('status', 'pending')

    merge_requests = UserMergeRequest.objects.select_related(
        'requesting_user',
        'primary_user',
        'reviewed_by'
    )

    if status_filter and status_filter != 'all':
        merge_requests = merge_requests.filter(status=status_filter)

    merge_requests = merge_requests.order_by('-created_at')

    # Pagination
    paginator = Paginator(merge_requests, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'merge_requests': page_obj,
        'status_filter': status_filter,
        'status_choices': UserMergeRequest.Status.choices,
    }

    return render(request, 'accounts/merge_requests_list.html', context)


@staff_member_required
def merge_request_detail(request, pk):
    """
    Нэгтгэх хүсэлтийн дэлгэрэнгүй (хянах, баталгаажуулах)
    """
    from ..models import UserMergeRequest
    from olympiad.models import ScoreSheet, Result

    merge_request = get_object_or_404(
        UserMergeRequest.objects.select_related(
            'requesting_user',
            'primary_user',
            'reviewed_by'
        ),
        pk=pk
    )

    # Get users involved
    users = merge_request.get_users().select_related('data__province', 'data__school', 'data__grade')

    # Check for missing users (deleted after merge)
    existing_user_ids = set(users.values_list('id', flat=True))
    requested_user_ids = set(merge_request.user_ids)
    missing_user_ids = requested_user_ids - existing_user_ids

    if missing_user_ids:
        messages.warning(
            request,
            f"Анхаар: {len(missing_user_ids)} хэрэглэгч олдсонгүй (ID: {', '.join(map(str, missing_user_ids))}). "
            f"Магадгүй өмнө нь нэгтгэгдсэн байж болзошгүй."
        )

    # Get olympiad participation for each user
    user_olympiads = {}
    for user in users:
        # Get all scoresheets
        scoresheets = ScoreSheet.objects.filter(user=user).select_related('olympiad')

        # Get all results
        results = Result.objects.filter(contestant=user).select_related('olympiad', 'problem')

        # Combine olympiad IDs
        olympiad_ids = set()
        olympiad_ids.update(scoresheets.values_list('olympiad_id', flat=True))
        olympiad_ids.update(results.values_list('olympiad_id', flat=True))

        user_olympiads[user.id] = {
            'user': user,
            'olympiad_count': len(olympiad_ids),
            'scoresheets': scoresheets,
            'results': results,
        }

    # Detect conflicts if not already done
    if not merge_request.conflicts_data:
        merge_request.detect_conflicts()
        merge_request.save()

    # Attach confirmation data to user objects for easier template access
    users_list = []
    for user in users:
        user_id_str = str(user.id)
        user.confirmation = merge_request.confirmations.get(user_id_str, {
            'status': 'unknown',
            'confirmed_at': None,
            'rejected_at': None,
        })
        users_list.append(user)

    context = {
        'merge_request': merge_request,
        'users': users_list,
        'user_olympiads': user_olympiads,
        'conflicts': merge_request.conflicts_data or [],
    }

    return render(request, 'accounts/merge_request_detail.html', context)


@staff_member_required
def merge_request_approve(request, pk):
    """
    Нэгтгэх хүсэлтийг баталгаажуулж, автомат нэгтгэх
    """
    from ..models import UserMergeRequest
    from django.contrib.auth.models import User

    merge_request = get_object_or_404(UserMergeRequest, pk=pk)

    if request.method == 'POST':
        # Check if all users still exist
        users = merge_request.get_users()
        if users.count() < len(merge_request.user_ids):
            missing_ids = set(merge_request.user_ids) - set(users.values_list('id', flat=True))
            merge_request.status = UserMergeRequest.Status.REJECTED
            merge_request.reviewed_by = request.user
            merge_request.reviewed_at = timezone.now()
            merge_request.review_notes = f"Зарим хэрэглэгч олдсонгүй (ID: {', '.join(map(str, missing_ids))}). Магадгүй өмнө нь нэгтгэгдсэн байж болзошгүй."
            merge_request.save()

            messages.error(
                request,
                f"Нэгтгэх боломжгүй! {len(missing_ids)} хэрэглэгч олдсонгүй. "
                f"Магадгүй өмнө нь нэгтгэгдсэн байж болзошгүй."
            )
            return redirect('merge_request_detail', pk=pk)

        review_notes = request.POST.get('review_notes', '')
        primary_user_id = request.POST.get('primary_user_id')

        # Set primary user if specified
        if primary_user_id:
            try:
                primary_user = User.objects.get(id=int(primary_user_id))
                if primary_user.id in merge_request.user_ids:
                    merge_request.primary_user = primary_user
            except (User.DoesNotExist, ValueError):
                messages.error(request, "Буруу үндсэн хэрэглэгч сонгосон байна.")
                return redirect('merge_request_detail', pk=pk)

        # Check for conflicts one more time
        conflicts = merge_request.detect_conflicts()

        if conflicts:
            merge_request.status = UserMergeRequest.Status.REJECTED
            merge_request.reviewed_by = request.user
            merge_request.reviewed_at = timezone.now()
            merge_request.review_notes = f"Дүнгийн зөрчилтэй байгаа тул татгалзсан. {review_notes}"
            merge_request.save()

            messages.error(
                request,
                f"Нэгтгэх боломжгүй! {len(conflicts)} зөрчил илэрлээ. "
                f"Эхлээд мэдээллийн сангаас зөрчлийг засна уу."
            )
            return redirect('merge_request_detail', pk=pk)

        # Proceed with merge
        try:
            with transaction.atomic():
                success = _perform_merge(merge_request)

                if success:
                    merge_request.status = UserMergeRequest.Status.COMPLETED
                    merge_request.reviewed_by = request.user
                    merge_request.reviewed_at = timezone.now()
                    merge_request.review_notes = review_notes
                    merge_request.save()

                    messages.success(
                        request,
                        f"Амжилттай нэгтгэлээ! Хэрэглэгч #{merge_request.primary_user.id} руу "
                        f"{len(merge_request.user_ids)-1} хэрэглэгчийг нэгтгэлээ."
                    )
                else:
                    raise Exception("Нэгтгэх явцад алдаа гарлаа")

        except Exception as e:
            merge_request.status = UserMergeRequest.Status.FAILED
            merge_request.merge_error = str(e)
            merge_request.reviewed_by = request.user
            merge_request.reviewed_at = timezone.now()
            merge_request.save()

            messages.error(request, f"Нэгтгэхэд алдаа гарлаа: {str(e)}")
            return redirect('merge_request_detail', pk=pk)

        return redirect('merge_requests_list')

    return redirect('merge_request_detail', pk=pk)


@staff_member_required
def merge_request_reject(request, pk):
    """
    Нэгтгэх хүсэлтийг татгалзах
    """
    from ..models import UserMergeRequest

    merge_request = get_object_or_404(UserMergeRequest, pk=pk)

    if request.method == 'POST':
        review_notes = request.POST.get('review_notes', '')

        merge_request.status = UserMergeRequest.Status.REJECTED
        merge_request.reviewed_by = request.user
        merge_request.reviewed_at = timezone.now()
        merge_request.review_notes = review_notes
        merge_request.save()

        messages.success(request, "Нэгтгэх хүсэлтийг татгалзлаа.")
        return redirect('merge_requests_list')

    return redirect('merge_request_detail', pk=pk)


def _perform_merge(merge_request):
    """
    Нэгтгэх үйлдлийг гүйцэтгэх (automerge_users.py-н логикийг ашиглана)
    """
    from olympiad.models import Result, Award, Comment, ScoreSheet
    from schools.models import School
    from ..models import UserMeta
    from django.contrib.auth.models import User

    users = list(merge_request.get_users())

    # Sort by last login
    users.sort(
        key=lambda u: u.last_login or timezone.make_aware(datetime.datetime.min),
        reverse=True
    )

    # Determine primary user
    if merge_request.primary_user:
        primary_user = merge_request.primary_user
        duplicate_users = [u for u in users if u.id != primary_user.id]
    else:
        primary_user = users[0]
        duplicate_users = users[1:]

    # Ensure primary user has UserMeta
    primary_meta, _ = UserMeta.objects.get_or_create(user=primary_user)

    # Collect best data from all users
    best_data = {'user': {}, 'meta': {}}
    all_users_for_merge = [primary_user] + duplicate_users

    cyrillic_pattern = re.compile(r'[а-яА-ЯөӨүҮ]')
    def is_cyrillic(s):
        return s and bool(cyrillic_pattern.search(s))

    for user in all_users_for_merge:
        # Prefer Cyrillic names
        current_best_fn = best_data['user'].get('first_name')
        if user.first_name and (not current_best_fn or
            (is_cyrillic(user.first_name) and not is_cyrillic(current_best_fn))):
            best_data['user']['first_name'] = user.first_name

        current_best_ln = best_data['user'].get('last_name')
        if user.last_name and (not current_best_ln or
            (is_cyrillic(user.last_name) and not is_cyrillic(current_best_ln))):
            best_data['user']['last_name'] = user.last_name

        if not best_data['user'].get('email') and user.email:
            best_data['user']['email'] = user.email

        if hasattr(user, 'data'):
            meta = user.data
            if not best_data['meta'].get('school') and meta.school:
                best_data['meta']['school'] = meta.school
            if not best_data['meta'].get('grade') and meta.grade:
                best_data['meta']['grade'] = meta.grade
            if not best_data['meta'].get('mobile') and meta.mobile:
                best_data['meta']['mobile'] = meta.mobile
            if not best_data['meta'].get('reg_num') and meta.reg_num:
                best_data['meta']['reg_num'] = meta.reg_num

    # Apply best data to primary user
    for field, value in best_data['user'].items():
        setattr(primary_user, field, value)
    primary_user.save()

    for field, value in best_data['meta'].items():
        setattr(primary_meta, field, value)
    primary_meta.save()

    # Migrate relationships
    for dup_user in duplicate_users:
        # Add groups
        duplicate_user_groups = dup_user.groups.all()
        primary_user.groups.add(*duplicate_user_groups)

        # Update foreign keys
        Result.objects.filter(contestant=dup_user).update(contestant=primary_user)
        Award.objects.filter(contestant=dup_user).update(contestant=primary_user)
        Comment.objects.filter(author=dup_user).update(author=primary_user)
        ScoreSheet.objects.filter(user=dup_user).update(user=primary_user)
        School.objects.filter(user=dup_user).update(user=primary_user)
        School.objects.filter(manager=dup_user).update(manager=primary_user)

        # Delete duplicate user
        dup_user.delete()

    return True