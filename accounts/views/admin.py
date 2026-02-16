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
    from ..models import Province, Zone, UserMergeRequest

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

    # Users by province (province is on UserMeta, related_name='data')
    from ..models import UserMeta
    users_by_province = (
        UserMeta.objects
        .values('province__name')
        .annotate(count=Count('user'))
        .order_by('-count')
    )

    # School statistics
    total_schools = School.objects.count()

    # Olympiad statistics
    total_olympiads = Olympiad.objects.count()
    total_results = Result.objects.count()

    # Province / Zone
    total_provinces = Province.objects.count()
    provinces_no_contact = Province.objects.filter(contact_person__isnull=True).count()
    total_zones = Zone.objects.count()
    zones_no_contact = Zone.objects.filter(contact_person__isnull=True).count()

    # Merge requests
    pending_merges = UserMergeRequest.objects.filter(status='pending').count()

    # Recent users
    recent_users = User.objects.select_related('data__province').order_by('-date_joined')[:10]

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
        'total_provinces': total_provinces,
        'provinces_no_contact': provinces_no_contact,
        'total_zones': total_zones,
        'zones_no_contact': zones_no_contact,
        'pending_merges': pending_merges,
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
    categories = [
        {
            'name': 'Олимпиад',
            'icon': 'fas fa-trophy',
            'color': 'primary',
            'commands': [
                {
                    'name': 'generate_answer_sheet',
                    'description': 'Сурагчдын мэдээллээр урьдчилан дүүргэсэн 2 sheet-тэй Excel загвар файл үүсгэнэ.',
                    'usage': 'python manage.py generate_answer_sheet --olympiad-id ID --school-id ID --output-file FILE',
                    'args': '--olympiad-id, --school-id, --output-file (заавал), --test (туршилт)',
                    'examples': [
                        'python manage.py generate_answer_sheet --olympiad-id 55 --school-id 42 --output-file ./olymp55.xlsx',
                        'python manage.py generate_answer_sheet --olympiad-id 55 --school-id 42 --output-file ./test.xlsx --test',
                    ],
                    'danger': False,
                },
                {
                    'name': 'import_answers_from_excel',
                    'description': 'Хавтас доторх бүх Excel файлаас олимпиадын хариултыг импортолно. ID, овог нэр, сургуулийн харьяалал зэргийг шалгана.',
                    'usage': 'python manage.py import_answers_from_excel --directory PATH',
                    'args': '--directory (заавал)',
                    'examples': [
                        'python manage.py import_answers_from_excel --directory /home/deploy/answer_sheets/',
                    ],
                    'danger': False,
                },
                {
                    'name': 'import_scores_from_excel',
                    'description': 'Хавтас доторх бүх Excel файлаас олимпиадын оноог импортолно.',
                    'usage': 'python manage.py import_scores_from_excel --directory PATH',
                    'args': '--directory (заавал), --force-import (групп шалгахгүй)',
                    'examples': [
                        'python manage.py import_scores_from_excel --directory /home/deploy/scores/',
                    ],
                    'danger': False,
                },
                {
                    'name': 'universal_import',
                    'description': 'Excel файлаас олимпиадын хариулт, оноог уншиж нэгдсэн форматаар импортолно.',
                    'usage': 'python manage.py universal_import --directory PATH',
                    'args': '--directory (заавал)',
                    'examples': [],
                    'danger': False,
                },
                {
                    'name': 'calculate_scores',
                    'description': 'Тестийн олимпиадын оноог автоматаар тооцоолно.',
                    'usage': 'python manage.py calculate_scores OLYMPIAD_ID [OLYMPIAD_ID ...]',
                    'args': 'олимпиад ID-ууд (нэг буюу олон)',
                    'examples': [
                        'python manage.py calculate_scores 55 56 57',
                    ],
                    'danger': False,
                },
                {
                    'name': 'generate_scoresheets',
                    'description': 'Result-аас ScoreSheet үүсгэж, улсын, аймгийн, бүсийн эрэмбийг тооцоолно.',
                    'usage': 'python manage.py generate_scoresheets OLYMPIAD_ID [...]',
                    'args': 'олимпиад ID-ууд (нэг буюу олон), --force-delete, --log-file',
                    'examples': [
                        'python manage.py generate_scoresheets 77',
                        'python manage.py generate_scoresheets 77 --force-delete',
                    ],
                    'danger': False,
                },
                {
                    'name': 'first_to_second_by_ranking',
                    'description': '1-р давааны үр дүнгээс 2-р даваанд шалгарах сурагчдыг сонгоно.',
                    'usage': 'python manage.py first_to_second_by_ranking --config-file FILE [--dry-run]',
                    'args': '--config-file (заавал), --dry-run',
                    'examples': [
                        'python manage.py first_to_second_by_ranking --config-file quota.xlsx --dry-run',
                        'python manage.py first_to_second_by_ranking --config-file quota.xlsx',
                    ],
                    'danger': True,
                },
                {
                    'name': 'second_to_third_fourth_by_ranking',
                    'description': '2-р давааны үр дүнгээс 3-р болон 4-р даваанд шалгарах сурагчдыг сонгоно.',
                    'usage': 'python manage.py second_to_third_fourth_by_ranking --config-file FILE [--dry-run]',
                    'args': '--config-file (заавал), --dry-run, --max-fourth-per-province N, --log-file',
                    'examples': [
                        'python manage.py second_to_third_fourth_by_ranking --config-file quota.xlsx --dry-run',
                        'python manage.py second_to_third_fourth_by_ranking --config-file quota.xlsx',
                    ],
                    'danger': True,
                },
                {
                    'name': 'add_info_sheet',
                    'description': 'Excel файлуудад Мэдээлэл sheet нэмнэ.',
                    'usage': 'python manage.py add_info_sheet FOLDER [--province-id ID]',
                    'args': 'folder (заавал), --province-id',
                    'examples': [
                        'python manage.py add_info_sheet /home/deploy/sheets/ --province-id 5',
                    ],
                    'danger': False,
                },
                {
                    'name': 'clone_olympiad',
                    'description': 'Олимпиадыг бүх бодлогын хамт хуулбарлаж, шинэ хичээлийн жилд оноох.',
                    'usage': 'python manage.py clone_olympiad SOURCE_ID NEW_YEAR_ID [--new-name NAME]',
                    'args': 'source_olympiad_id, new_school_year_id, --new-name',
                    'examples': [
                        'python manage.py clone_olympiad 55 3 --new-name "ММО 2025"',
                    ],
                    'danger': False,
                },
                {
                    'name': 'clone_school_year',
                    'description': 'Нэг хичээлийн жилийн бүх олимпиад, бодлогыг нөгөө жил рүү хуулна.',
                    'usage': 'python manage.py clone_school_year OLD_ID NEW_ID',
                    'args': 'old_id, new_id',
                    'examples': [
                        'python manage.py clone_school_year 2 3',
                    ],
                    'danger': False,
                },
                {
                    'name': 'delete_olympiad',
                    'description': 'Олимпиадыг бүх холбоотой мэдээллийн хамт устгана.',
                    'usage': 'python manage.py delete_olympiad OLYMPIAD_ID',
                    'args': 'olympiad_id',
                    'examples': [
                        'python manage.py delete_olympiad 99',
                    ],
                    'danger': True,
                },
                {
                    'name': 'merge_olympiads',
                    'description': 'Олимпиадуудыг нэг үндсэн олимпиад руу нэгтгэнэ.',
                    'usage': 'python manage.py merge_olympiads --primary-olympiad-id ID --duplicate-olympiad-ids ID [ID ...]',
                    'args': '--primary-olympiad-id (заавал), --duplicate-olympiad-ids (заавал)',
                    'examples': [
                        'python manage.py merge_olympiads --primary-olympiad-id 55 --duplicate-olympiad-ids 56 57',
                    ],
                    'danger': True,
                },
                {
                    'name': 'find_duplicates',
                    'description': 'Олимпиадад нэг сургуульд ижил овог нэртэй давхардсан сурагчдыг олно.',
                    'usage': 'python manage.py find_duplicates OLYMPIAD_ID',
                    'args': 'olympiad_id',
                    'examples': [
                        'python manage.py find_duplicates 55',
                    ],
                    'danger': False,
                },
                {
                    'name': 'classify_problems',
                    'description': 'Бодлогын statement-г keyword-д суурилж ангилна.',
                    'usage': 'python manage.py classify_problems [--dry-run]',
                    'args': '--dry-run',
                    'examples': [
                        'python manage.py classify_problems --dry-run',
                    ],
                    'danger': False,
                },
            ],
        },
        {
            'name': 'Хэрэглэгч',
            'icon': 'fas fa-users',
            'color': 'success',
            'commands': [
                {
                    'name': 'find_duplicate_users',
                    'description': 'Давхардсан болон буруу форматтай регистрийн дугаартай хэрэглэгчдийг илрүүлнэ. Өөрчлөлт хийхгүй.',
                    'usage': 'python manage.py find_duplicate_users',
                    'args': '(аргумент байхгүй)',
                    'examples': [],
                    'danger': False,
                },
                {
                    'name': 'find_duplicate_school_users',
                    'description': 'Хоёр ба түүнээс дээш сургуультай хэрэглэгчдийг олж харуулна.',
                    'usage': 'python manage.py find_duplicate_school_users',
                    'args': '(аргумент байхгүй)',
                    'examples': [],
                    'danger': False,
                },
                {
                    'name': 'automerge_users',
                    'description': 'Давхардсан хэрэглэгчдийг регистр, овог нэрээр ухаалгаар нэгтгэнэ. Дүнгийн зөрчлийг шалгадаг.',
                    'usage': 'python manage.py automerge_users [--all | --reg-num REG]',
                    'args': '--all (бүгд), --reg-num (нэг регистр), --no-input, --similarity-threshold N',
                    'examples': [
                        'python manage.py automerge_users --all',
                        'python manage.py automerge_users --reg-num УБ00112233',
                    ],
                    'danger': True,
                },
                {
                    'name': 'advance_grades',
                    'description': 'Бүх сурагчдын ангийг нэгээр ахиулж, төгсөгчдийг тохируулна. Жил бүр нэг удаа.',
                    'usage': 'python manage.py advance_grades',
                    'args': '(аргумент байхгүй)',
                    'examples': [],
                    'danger': True,
                },
                {
                    'name': 'delete_inactive_users',
                    'description': 'Заасан хугацаанд нэвтрээгүй хэрэглэгчдийг устгана.',
                    'usage': 'python manage.py delete_inactive_users [--days N] [--dry-run]',
                    'args': '--days N (default: 365), --dry-run, --confirm',
                    'examples': [
                        'python manage.py delete_inactive_users --days 365 --dry-run',
                        'python manage.py delete_inactive_users --days 365 --confirm',
                    ],
                    'danger': True,
                },
                {
                    'name': 'delete_auto_users',
                    'description': 'auto-user@mmo.mn имэйлтэй хэрэглэгчдийг бүх холбоотой мэдээллийн хамт устгана.',
                    'usage': 'python manage.py delete_auto_users [--dry-run] [--confirm]',
                    'args': '--dry-run, --confirm',
                    'examples': [
                        'python manage.py delete_auto_users --dry-run',
                        'python manage.py delete_auto_users --confirm',
                    ],
                    'danger': True,
                },
                {
                    'name': 'import_user_groups',
                    'description': 'CSV файлаас хэрэглэгч-группийн холбоог сэргээнэ.',
                    'usage': 'python manage.py import_user_groups CSV_PATH',
                    'args': 'csv_path (заавал)',
                    'examples': [
                        'python manage.py import_user_groups auth_user_groups.csv',
                    ],
                    'danger': False,
                },
                {
                    'name': 'import_user_school_name',
                    'description': 'CSV файлаас user_school_name баганыг UserMeta руу импортолно.',
                    'usage': 'python manage.py import_user_school_name CSV_PATH',
                    'args': 'csv_path (заавал)',
                    'examples': [],
                    'danger': False,
                },
                {
                    'name': 'update_students_school_from_group',
                    'description': 'School.group-д харьяалагдаж буй хэрэглэгчдийн UserMeta.school-г шинэчилнэ.',
                    'usage': 'python manage.py update_students_school_from_group',
                    'args': '(аргумент байхгүй)',
                    'examples': [],
                    'danger': False,
                },
                {
                    'name': 'import_province_managers',
                    'description': 'Аймаг/дүүргүүдийн боловсролын мэргэжилтнүүдийг Excel файлаас импортолно.',
                    'usage': 'python manage.py import_province_managers EXCEL_FILE [--dry-run]',
                    'args': 'excel_file (заавал), --dry-run',
                    'examples': [
                        'python manage.py import_province_managers managers.xlsx --dry-run',
                    ],
                    'danger': False,
                },
                {
                    'name': 'fill_school_prediction',
                    'description': 'SchoolData-г хамгийн төстэй School-оор автоматаар нөхнө.',
                    'usage': 'python manage.py fill_school_prediction',
                    'args': '(аргумент байхгүй)',
                    'examples': [],
                    'danger': False,
                },
                {
                    'name': 'cleanup_orphan_schooldata',
                    'description': 'User хүснэгтэд байхгүй user_id-тэй SchoolData мөрүүдийг устгана.',
                    'usage': 'python manage.py cleanup_orphan_schooldata',
                    'args': '(аргумент байхгүй)',
                    'examples': [],
                    'danger': True,
                },
            ],
        },
        {
            'name': 'Сургууль',
            'icon': 'fas fa-school',
            'color': 'info',
            'commands': [
                {
                    'name': 'export_schools_excel',
                    'description': 'Сургуулиудын нэр, ID бүхий Excel файл үүсгэнэ (аймаг бүрээр тусдаа).',
                    'usage': 'python manage.py export_schools_excel [--output-dir DIR]',
                    'args': '--output-dir (default: schools_export)',
                    'examples': [
                        'python manage.py export_schools_excel --output-dir /home/deploy/export/',
                    ],
                    'danger': False,
                },
                {
                    'name': 'show_school_staff',
                    'description': 'Тодорхой удирдагч багшийн удирдаж буй сургуулиудын ажилтнуудыг харуулна.',
                    'usage': 'python manage.py show_school_staff USERNAME',
                    'args': 'username (заавал)',
                    'examples': [
                        'python manage.py show_school_staff admin',
                    ],
                    'danger': False,
                },
                {
                    'name': 'check_moderator_school',
                    'description': 'Удирдагч багшийн профайл дээрх сургууль нь удирдаж буй сургуультайгаа зөрч буй эсэхийг шалгана.',
                    'usage': 'python manage.py check_moderator_school',
                    'args': '(аргумент байхгүй)',
                    'examples': [],
                    'danger': False,
                },
                {
                    'name': 'sync_user_schools',
                    'description': 'Хэрэглэгчийн группт хамаарах сургуулийг UserMeta.school талбарт тохируулна.',
                    'usage': 'python manage.py sync_user_schools',
                    'args': '(аргумент байхгүй)',
                    'examples': [],
                    'danger': False,
                },
                {
                    'name': 'fixduplicateschools',
                    'description': 'Групптай давхардсан сургуулиудыг сүүлийн ID-тайг үлдээж устгана.',
                    'usage': 'python manage.py fixduplicateschools [--confirm]',
                    'args': '--confirm',
                    'examples': [
                        'python manage.py fixduplicateschools',
                        'python manage.py fixduplicateschools --confirm',
                    ],
                    'danger': True,
                },
                {
                    'name': 'create_school_managers',
                    'description': 'Сургууль бүрт менежер хэрэглэгч үүсгэнэ.',
                    'usage': 'python manage.py create_school_managers [--dry-run]',
                    'args': '--dry-run',
                    'examples': [
                        'python manage.py create_school_managers --dry-run',
                    ],
                    'danger': True,
                },
                {
                    'name': 'create_busad_schools',
                    'description': 'Province бүрд "Бусад" нэртэй сургууль үүсгэнэ.',
                    'usage': 'python manage.py create_busad_schools [--dry-run]',
                    'args': '--dry-run',
                    'examples': [
                        'python manage.py create_busad_schools --dry-run',
                    ],
                    'danger': False,
                },
                {
                    'name': 'search_excel',
                    'description': 'Excel файлуудаас түлхүүр үг хайна.',
                    'usage': 'python manage.py search_excel --folder PATH --keyword TEXT',
                    'args': '--folder (заавал), --keyword (заавал), --case-sensitive',
                    'examples': [
                        'python manage.py search_excel --folder /home/deploy/sheets/ --keyword "Батболд"',
                    ],
                    'danger': False,
                },
            ],
        },
        {
            'name': 'Бүртгэл',
            'icon': 'fas fa-clipboard-list',
            'color': 'warning',
            'commands': [
                {
                    'name': 'delete_round2_groups',
                    'description': 'Round2 бүх бүлгийг устгана (олимпиадын group-ыг null болгож, бүлгийг устгана).',
                    'usage': 'python manage.py delete_round2_groups [--dry-run]',
                    'args': '--dry-run',
                    'examples': [
                        'python manage.py delete_round2_groups --dry-run',
                        'python manage.py delete_round2_groups',
                    ],
                    'danger': True,
                },
            ],
        },
    ]

    # Нийт коммандын тоо
    total_commands = sum(len(cat['commands']) for cat in categories)

    context = {
        'categories': categories,
        'total_commands': total_commands,
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
    from schools.models import School

    merge_request = get_object_or_404(
        UserMergeRequest.objects.select_related(
            'requesting_user',
            'primary_user',
            'reviewed_by'
        ),
        pk=pk
    )

    # Get users involved
    users = merge_request.get_users().select_related(
        'data__province', 'data__school', 'data__grade', 'data__level')

    # Check for missing users (deleted after merge)
    existing_user_ids = set(users.values_list('id', flat=True))
    requested_user_ids = set(merge_request.user_ids)
    missing_user_ids = requested_user_ids - existing_user_ids

    if missing_user_ids and merge_request.status == 'pending':
        messages.warning(
            request,
            f"Анхаар: {len(missing_user_ids)} хэрэглэгч олдсонгүй (ID: {', '.join(map(str, missing_user_ids))}). "
            f"Магадгүй өмнө нь нэгтгэгдсэн байж болзошгүй."
        )

    # Sort users by last login
    users_list = list(users)
    users_list.sort(
        key=lambda u: u.last_login or timezone.make_aware(datetime.datetime.min),
        reverse=True
    )

    # Get olympiad participation for each user
    user_olympiads = {}
    for user in users_list:
        scoresheets = ScoreSheet.objects.filter(user=user).select_related('olympiad')
        results = Result.objects.filter(contestant=user).select_related('olympiad', 'problem')
        olympiad_ids = set()
        olympiad_ids.update(scoresheets.values_list('olympiad_id', flat=True))
        olympiad_ids.update(results.values_list('olympiad_id', flat=True))

        user_olympiads[user.id] = {
            'user': user,
            'olympiad_count': len(olympiad_ids),
            'scoresheets': scoresheets,
            'results': results,
        }

    # Extract saved field_selections from conflicts_data (sent by school/province merge request)
    saved_field_selections = {}
    if isinstance(merge_request.conflicts_data, dict):
        saved_field_selections = merge_request.conflicts_data.get('field_selections', {})

    # Attach confirmation data to user objects for easier template access
    for user in users_list:
        user_id_str = str(user.id)
        user.confirmation = merge_request.confirmations.get(user_id_str, {
            'status': 'unknown',
            'confirmed_at': None,
            'rejected_at': None,
        })

    # Determine primary user for field comparison
    primary_user = merge_request.primary_user
    primary_id = primary_user.id if primary_user else (users_list[0].id if users_list else None)

    # Build field comparison data (like school merge step 2)
    compare_fields = []
    field_defs = [
        ('last_name', 'Овог', 'user'),
        ('first_name', 'Нэр', 'user'),
        ('email', 'Имэйл', 'user'),
        ('reg_num', 'РД', 'meta'),
        ('school', 'Сургууль', 'meta_fk'),
        ('province', 'Аймаг', 'meta_fk'),
        ('grade', 'Анги', 'meta_fk'),
        ('level', 'Ангилал', 'meta_fk'),
        ('mobile', 'Утас', 'meta'),
        ('gender', 'Хүйс', 'meta'),
    ]

    for field_name, label, field_type in field_defs:
        values = []
        for u in users_list:
            if field_type == 'user':
                val = getattr(u, field_name, '') or ''
                values.append({'user_id': u.id, 'value': str(val), 'raw_value': str(val)})
            elif field_type == 'meta':
                meta = getattr(u, 'data', None)
                val = getattr(meta, field_name, '') if meta else ''
                val = val if val is not None else ''
                values.append({'user_id': u.id, 'value': str(val), 'raw_value': str(val)})
            elif field_type == 'meta_fk':
                meta = getattr(u, 'data', None)
                obj = getattr(meta, field_name, None) if meta else None
                display = str(obj) if obj else ''
                raw = str(obj.id) if obj else ''
                values.append({'user_id': u.id, 'value': display, 'raw_value': raw})

        non_empty = [v['value'] for v in values if v['value']]
        unique_values = set(non_empty)
        is_different = len(unique_values) > 1

        # Use saved field selection if available (from requester's choices)
        saved_val = saved_field_selections.get(field_name)
        if saved_val:
            auto_selected = str(saved_val)
            # Find display value
            matched = next((v for v in values if v['raw_value'] == auto_selected), None)
            auto_selected_display = matched['value'] if matched else auto_selected
        else:
            primary_val = next((v for v in values if v['user_id'] == primary_id), None)
            if primary_val and primary_val['raw_value']:
                auto_selected = primary_val['raw_value']
                auto_selected_display = primary_val['value']
            else:
                first_non_empty = next((v for v in values if v['raw_value']), None)
                auto_selected = first_non_empty['raw_value'] if first_non_empty else ''
                auto_selected_display = first_non_empty['value'] if first_non_empty else ''

        compare_fields.append({
            'name': field_name,
            'label': label,
            'field_type': field_type,
            'values': values,
            'is_different': is_different,
            'all_empty': len(non_empty) == 0,
            'auto_selected': auto_selected,
            'auto_selected_display': auto_selected_display,
        })

    # Build result conflicts with selectable options
    result_conflicts = []
    if primary_id:
        duplicate_users_for_conflicts = [u for u in users_list if u.id != primary_id]
        for dup_user in duplicate_users_for_conflicts:
            dup_results = Result.objects.filter(contestant=dup_user).select_related('olympiad', 'problem')
            for dup_result in dup_results:
                primary_result = Result.objects.filter(
                    contestant_id=primary_id,
                    olympiad=dup_result.olympiad,
                    problem=dup_result.problem
                ).first()
                if primary_result and (primary_result.answer != dup_result.answer or primary_result.score != dup_result.score):
                    conflict_key = f"conflict_{dup_result.olympiad.id}_{dup_result.problem.id}"
                    result_conflicts.append({
                        'key': conflict_key,
                        'dup_user_id': dup_user.id,
                        'dup_user_name': f"{dup_user.last_name} {dup_user.first_name}",
                        'olympiad_id': dup_result.olympiad.id,
                        'olympiad_name': dup_result.olympiad.name,
                        'problem_id': dup_result.problem.id,
                        'problem_order': dup_result.problem.order,
                        'primary_score': primary_result.score,
                        'dup_score': dup_result.score,
                        'primary_answer': primary_result.answer,
                        'dup_answer': dup_result.answer,
                        'primary_result_id': primary_result.id,
                        'dup_result_id': dup_result.id,
                    })

    # Get all schools for dropdown
    all_schools = School.objects.all().order_by('name')

    # Build readable display of requester's selections
    saved_selections_display = []
    if saved_field_selections:
        field_labels = {
            'last_name': 'Овог', 'first_name': 'Нэр', 'email': 'Имэйл',
            'reg_num': 'РД', 'school': 'Сургууль', 'province': 'Аймаг',
            'grade': 'Анги', 'level': 'Ангилал', 'mobile': 'Утас', 'gender': 'Хүйс',
        }
        from ..models import Province, Grade, Level
        fk_fields = {'school': School, 'province': Province, 'grade': Grade, 'level': Level}
        for fn, val in saved_field_selections.items():
            label = field_labels.get(fn, fn)
            if fn in fk_fields and val:
                try:
                    obj = fk_fields[fn].objects.get(id=int(val))
                    display_val = str(obj)
                except (fk_fields[fn].DoesNotExist, ValueError):
                    display_val = val
            else:
                display_val = val
            saved_selections_display.append({'label': label, 'value': display_val})

    context = {
        'merge_request': merge_request,
        'users': users_list,
        'user_olympiads': user_olympiads,
        'conflicts': merge_request.conflicts_data or [],
        'compare_fields': compare_fields,
        'result_conflicts': result_conflicts,
        'primary_id': primary_id,
        'all_schools': all_schools,
        'saved_field_selections': saved_field_selections,
        'saved_selections_display': saved_selections_display,
    }

    return render(request, 'accounts/merge_request_detail.html', context)


@staff_member_required
def merge_request_approve(request, pk):
    """
    Нэгтгэх хүсэлтийг баталгаажуулж, автомат нэгтгэх
    """
    from ..models import UserMergeRequest, UserMeta
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

        # Collect field selections from form
        all_field_names = ['last_name', 'first_name', 'email', 'reg_num', 'school',
                           'province', 'grade', 'level', 'mobile', 'gender']
        field_selections = {}
        for fn in all_field_names:
            val = request.POST.get(f'field_{fn}', '').strip()
            if val:
                field_selections[fn] = val

        # Collect conflict resolutions
        conflict_resolutions = {}
        for key, val in request.POST.items():
            if key.startswith('conflict_'):
                conflict_resolutions[key] = val

        # Proceed with merge
        try:
            with transaction.atomic():
                success = _perform_merge(
                    merge_request,
                    field_selections=field_selections,
                    conflict_resolutions=conflict_resolutions,
                )

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


def _perform_merge(merge_request, field_selections=None, conflict_resolutions=None):
    """
    Нэгтгэх үйлдлийг гүйцэтгэх.
    field_selections: dict of field_name -> value (админ сонгосон утгууд)
    conflict_resolutions: dict of conflict_key -> 'primary' or 'dup' (дүнгийн зөрчил шийдвэр)
    """
    from olympiad.models import Result, Award, Comment, ScoreSheet
    from schools.models import School
    from ..models import UserMeta
    from django.contrib.auth.models import User

    field_selections = field_selections or {}
    conflict_resolutions = conflict_resolutions or {}

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

    if field_selections:
        # Apply admin-selected field values
        user_fields = ['last_name', 'first_name', 'email']
        for field in user_fields:
            value = field_selections.get(field, '')
            if value:
                setattr(primary_user, field, value)
        primary_user.save()

        meta_fields = ['reg_num', 'mobile', 'gender']
        meta_fk_fields = ['school', 'province', 'grade', 'level']

        for field in meta_fields:
            value = field_selections.get(field, '')
            if value:
                if field == 'mobile':
                    try:
                        setattr(primary_meta, field, int(value))
                    except ValueError:
                        pass
                else:
                    setattr(primary_meta, field, value)

        for field in meta_fk_fields:
            value = field_selections.get(field, '')
            if value:
                try:
                    setattr(primary_meta, f'{field}_id', int(value))
                except ValueError:
                    pass

        primary_meta.save()
    else:
        # Legacy auto-select: collect best data from all users
        best_data = {'user': {}, 'meta': {}}
        all_users_for_merge = [primary_user] + duplicate_users

        cyrillic_pattern = re.compile(r'[а-яА-ЯөӨүҮ]')
        def is_cyrillic(s):
            return s and bool(cyrillic_pattern.search(s))

        for user in all_users_for_merge:
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

        for field, value in best_data['user'].items():
            setattr(primary_user, field, value)
        primary_user.save()

        for field, value in best_data['meta'].items():
            setattr(primary_meta, field, value)
        primary_meta.save()

    # Apply conflict resolutions (choose which Result to keep)
    if conflict_resolutions:
        for dup_user in duplicate_users:
            dup_results = Result.objects.filter(contestant=dup_user).select_related('olympiad', 'problem')
            for dup_result in dup_results:
                primary_result = Result.objects.filter(
                    contestant=primary_user,
                    olympiad=dup_result.olympiad,
                    problem=dup_result.problem
                ).first()
                if primary_result:
                    conflict_key = f"conflict_{dup_result.olympiad.id}_{dup_result.problem.id}"
                    choice = conflict_resolutions.get(conflict_key, 'primary')
                    if choice == 'dup':
                        # Use duplicate's answer and score
                        primary_result.answer = dup_result.answer
                        primary_result.score = dup_result.score
                        primary_result.save()
                    # Delete duplicate result either way
                    dup_result.delete()

    # Migrate relationships
    for dup_user in duplicate_users:
        # Add groups
        primary_user.groups.add(*dup_user.groups.all())

        # Update foreign keys (Results without conflicts already handled above)
        Result.objects.filter(contestant=dup_user).update(contestant=primary_user)
        Award.objects.filter(contestant=dup_user).update(contestant=primary_user)
        Comment.objects.filter(author=dup_user).update(author=primary_user)
        ScoreSheet.objects.filter(user=dup_user).update(user=primary_user)
        School.objects.filter(user=dup_user).update(user=primary_user)
        School.objects.filter(manager=dup_user).update(manager=primary_user)

        # Delete duplicate user
        dup_user.delete()

    return True


@staff_member_required
def province_contacts(request):
    """Бүх аймгуудын удирдах хүмүүсийг харах, солих, шинээр үүсгэх"""
    from ..models import Province, Zone
    from django.contrib.auth.models import User

    provinces = Province.objects.select_related('zone', 'contact_person').order_by('zone__name', 'name')
    zones = Zone.objects.select_related('contact_person').order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'change_province_contact':
            province_id = request.POST.get('province_id')
            user_id = request.POST.get('user_id', '').strip()
            province = get_object_or_404(Province, id=province_id)

            if not user_id:
                province.contact_person = None
                province.save(update_fields=['contact_person'])
                messages.success(request, f'"{province.name}" аймгийн удирдах хүнийг хаслаа.')
            else:
                try:
                    user = User.objects.get(id=int(user_id))
                    province.contact_person = user
                    province.save(update_fields=['contact_person'])
                    messages.success(request, f'"{province.name}" → {user.last_name} {user.first_name} (ID: {user.id})')
                except (ValueError, User.DoesNotExist):
                    messages.error(request, f'ID={user_id} хэрэглэгч олдсонгүй.')

        elif action == 'change_zone_contact':
            zone_id = request.POST.get('zone_id')
            user_id = request.POST.get('user_id', '').strip()
            zone = get_object_or_404(Zone, id=zone_id)

            if not user_id:
                zone.contact_person = None
                zone.save(update_fields=['contact_person'])
                messages.success(request, f'"{zone.name}" бүсийн удирдах хүнийг хаслаа.')
            else:
                try:
                    user = User.objects.get(id=int(user_id))
                    zone.contact_person = user
                    zone.save(update_fields=['contact_person'])
                    messages.success(request, f'"{zone.name}" → {user.last_name} {user.first_name} (ID: {user.id})')
                except (ValueError, User.DoesNotExist):
                    messages.error(request, f'ID={user_id} хэрэглэгч олдсонгүй.')

        elif action == 'create_and_assign_province':
            province_id = request.POST.get('province_id')
            province = get_object_or_404(Province, id=province_id)
            new_last_name = request.POST.get('new_last_name', '').strip()
            new_first_name = request.POST.get('new_first_name', '').strip()
            new_email = request.POST.get('new_email', '').strip()
            new_phone = request.POST.get('new_phone', '').strip()

            if not new_last_name or not new_first_name:
                messages.error(request, 'Овог, нэр заавал оруулна.')
            else:
                # Username: province_{id}_{timestamp}
                import time
                username = f'province_{province.id}_{int(time.time())}'
                user = User.objects.create_user(
                    username=username,
                    first_name=new_first_name,
                    last_name=new_last_name,
                    email=new_email,
                    password=User.objects.make_random_password(),
                )
                # UserMeta үүсгэх
                from ..models import UserMeta
                meta, _ = UserMeta.objects.get_or_create(user=user)
                meta.province = province
                if new_phone:
                    try:
                        meta.mobile = int(new_phone)
                    except ValueError:
                        pass
                meta.save()

                province.contact_person = user
                province.save(update_fields=['contact_person'])
                messages.success(request, f'"{province.name}" → шинэ хэрэглэгч {user.last_name} {user.first_name} (ID: {user.id}) үүсгэж холболоо.')

        elif action == 'create_and_assign_zone':
            zone_id = request.POST.get('zone_id')
            zone = get_object_or_404(Zone, id=zone_id)
            new_last_name = request.POST.get('new_last_name', '').strip()
            new_first_name = request.POST.get('new_first_name', '').strip()
            new_email = request.POST.get('new_email', '').strip()
            new_phone = request.POST.get('new_phone', '').strip()

            if not new_last_name or not new_first_name:
                messages.error(request, 'Овог, нэр заавал оруулна.')
            else:
                import time
                username = f'zone_{zone.id}_{int(time.time())}'
                user = User.objects.create_user(
                    username=username,
                    first_name=new_first_name,
                    last_name=new_last_name,
                    email=new_email,
                    password=User.objects.make_random_password(),
                )
                from ..models import UserMeta
                meta, _ = UserMeta.objects.get_or_create(user=user)
                if new_phone:
                    try:
                        meta.mobile = int(new_phone)
                    except ValueError:
                        pass
                meta.save()

                zone.contact_person = user
                zone.save(update_fields=['contact_person'])
                messages.success(request, f'"{zone.name}" → шинэ хэрэглэгч {user.last_name} {user.first_name} (ID: {user.id}) үүсгэж холболоо.')

        return redirect('province_contacts')

    context = {
        'provinces': provinces,
        'zones': zones,
    }
    return render(request, 'accounts/province_contacts.html', context)