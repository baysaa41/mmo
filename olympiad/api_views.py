"""
API endpoints for external systems to access olympiad data
Requires API key authentication
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from olympiad.models import Olympiad, Problem, AnswerChoice, Topic, ScoreSheet


def check_api_key(request):
    """API key шалгах"""
    api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')
    expected_key = getattr(settings, 'MMO_API_KEY', None)

    if not expected_key:
        # API key тохируулаагүй бол нээлттэй үлдээх (хуучин хэлбэр)
        return True

    return api_key == expected_key


@csrf_exempt
@require_http_methods(["GET"])
def list_olympiads(request):
    """
    Олимпиадуудын жагсаалт
    GET /api/olympiads/
    Query params:
    - limit: default 100
    - offset: default 0
    Headers:
    - X-API-Key: API key for authentication
    """
    # API key шалгах
    if not check_api_key(request):
        return JsonResponse({'error': 'Invalid or missing API key'}, status=401)

    limit = int(request.GET.get('limit', 100))
    offset = int(request.GET.get('offset', 0))

    olympiads = Olympiad.objects.select_related(
        'school_year', 'level', 'host'
    ).annotate(
        problem_count=models.Count('problem')
    ).filter(
        problem_count__gt=0
    ).order_by('-school_year__name', '-round', '-month')

    total_count = olympiads.count()
    olympiads = olympiads[offset:offset + limit]

    results = []
    for olympiad in olympiads:
        results.append({
            'id': olympiad.id,
            'name': str(olympiad),  # Uses __str__ method
            'round': olympiad.round,
            'round_name': olympiad.get_round_display() if hasattr(olympiad, 'get_round_display') else _get_round_name(olympiad.round),
            'type': olympiad.type,
            'type_name': 'Уламжлалт' if olympiad.type == 0 else 'Тест',
            'school_year': olympiad.school_year.name if olympiad.school_year else None,
            'level': {
                'id': olympiad.level.id if olympiad.level else None,
                'name': olympiad.level.name if olympiad.level else None,
            },
            'host': olympiad.host.name if olympiad.host else None,
            'month': olympiad.month,
            'problem_count': olympiad.problem_count,
        })

    return JsonResponse({
        'count': total_count,
        'results': results
    })


@csrf_exempt
@require_http_methods(["GET"])
def olympiad_problems(request, olympiad_id):
    """
    Олимпиадын бодлогууд
    GET /api/olympiads/{olympiad_id}/problems/
    Headers:
    - X-API-Key: API key for authentication
    """
    # API key шалгах
    if not check_api_key(request):
        return JsonResponse({'error': 'Invalid or missing API key'}, status=401)

    try:
        olympiad = Olympiad.objects.select_related(
            'school_year', 'level', 'host'
        ).get(id=olympiad_id)
    except Olympiad.DoesNotExist:
        return JsonResponse({'error': 'Олимпиад олдсонгүй'}, status=404)

    problems = Problem.objects.filter(
        olympiad=olympiad
    ).prefetch_related(
        'topics', 'answerchoice_set'
    ).order_by('order')

    results = []
    for problem in problems:
        # Get topics
        topics = [topic.name for topic in problem.topics.all()]

        # Get answer choices for multiple choice problems
        choices = []
        if problem.type in [1, 2]:  # Selection or Fill-in
            for choice in problem.answerchoice_set.order_by('order'):
                choices.append({
                    'order': choice.order,
                    'label': choice.label,
                    'value': choice.value,
                    'points': choice.points,
                })

        results.append({
            'id': problem.id,
            'order': problem.order,
            'statement': problem.statement,
            'type': problem.type,
            'type_name': _get_problem_type_name(problem.type),
            'numerical_answer': problem.numerical_answer,
            'numerical_answer2': problem.numerical_answer2,
            'max_score': problem.max_score,
            'state': problem.state,
            'topics': topics,
            'answer_choices': choices,
        })

    return JsonResponse({
        'olympiad': {
            'id': olympiad.id,
            'name': str(olympiad),
            'round': olympiad.round,
            'round_name': _get_round_name(olympiad.round),
            'type': olympiad.type,
            'school_year': olympiad.school_year.name if olympiad.school_year else None,
            'level': {
                'id': olympiad.level.id if olympiad.level else None,
                'name': olympiad.level.name if olympiad.level else None,
            },
        },
        'problems': results
    })


def _get_round_name(round_val):
    """Олимпиадын шатны нэр"""
    round_names = {
        0: 'Бусад',
        1: 'Сургууль',
        2: 'Аймаг/Дүүрэг',
        3: 'Нийслэл/Бүс',
        4: 'Улсын',
        5: 'Олон улсын',
        6: 'Олон улсын бусад',
        7: 'Сонгон шалгаруулалт',
    }
    return round_names.get(round_val, 'Тодорхойгүй')


def _get_problem_type_name(ptype):
    """Бодлогын төрлийн нэр"""
    type_names = {
        0: 'Уламжлалт',
        1: 'Сонгох тест',
        2: 'Нөхөх тест',
    }
    return type_names.get(ptype, 'Тодорхойгүй')


@csrf_exempt
@require_http_methods(["GET"])
def user_achievements(request, user_id):
    """
    Хэрэглэгчийн олимпиадын түүх (MathMinds-аас дуудагдах API)
    GET /api/users/{user_id}/achievements/
    Headers:
    - X-API-Key: API key for authentication

    Response:
    {
        "user_id": 12345,
        "username": "student123",
        "achievements": [
            {
                "olympiad_id": 1,
                "olympiad_name": "2024 оны сургуулийн олимпиад - 9-р анги",
                "round": 1,
                "round_name": "Сургууль",
                "school_year": "2024-2025",
                "level_name": "9-р анги",
                "total_score": 42,
                "problems_solved": 5,
                "prizes": "Алтан медаль"
            },
            ...
        ],
        "statistics": {
            "total_olympiads": 3,
            "total_score": 98,
            "prizes_count": 2,
            "first_round_count": 1
        }
    }
    """
    # API key шалгах
    if not check_api_key(request):
        return JsonResponse({'error': 'Invalid or missing API key'}, status=401)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Хэрэглэгч олдсонгүй'}, status=404)

    # Хэрэглэгчийн бүх ScoreSheet-үүдийг авах
    scoresheets = ScoreSheet.objects.filter(
        user=user,
        olympiad__is_open=True
    ).select_related(
        'olympiad',
        'olympiad__level',
        'olympiad__school_year',
        'school'
    ).order_by('olympiad_id', '-id').distinct('olympiad_id')

    achievements = []
    first_round_count = 0
    total_score = 0
    prizes_count = 0

    for sheet in scoresheets:
        olympiad = sheet.olympiad

        # Бодлого шийдсэн тоо тоолох (0-ээс их оноотой)
        problems_solved = sum(
            1 for i in range(1, 21)
            if getattr(sheet, f's{i}', 0) and getattr(sheet, f's{i}', 0) > 0
        )

        # 1-р даваа эсэхийг шалгах
        if olympiad.round == 1:
            first_round_count += 1

        # Нийт оноо
        score = sheet.total or 0
        total_score += score

        # Шагнал
        has_prize = bool(sheet.prizes and sheet.prizes.strip())
        if has_prize:
            prizes_count += 1

        achievements.append({
            'olympiad_id': olympiad.id,
            'olympiad_name': str(olympiad),
            'round': olympiad.round,
            'round_name': _get_round_name(olympiad.round),
            'school_year': olympiad.school_year.name if olympiad.school_year else None,
            'level_name': olympiad.level.name if olympiad.level else None,
            'total_score': score,
            'problems_solved': problems_solved,
            'prizes': sheet.prizes or None
        })

    return JsonResponse({
        'user_id': user.id,
        'username': user.username,
        'achievements': achievements,
        'statistics': {
            'total_olympiads': len(achievements),
            'total_score': total_score,
            'prizes_count': prizes_count,
            'first_round_count': first_round_count
        }
    })
