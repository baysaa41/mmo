from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
import os
import platform

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