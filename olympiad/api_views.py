"""
API endpoints for external systems to access olympiad data
No authentication required
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from olympiad.models import Olympiad, Problem, AnswerChoice, Topic


@csrf_exempt
@require_http_methods(["GET"])
def list_olympiads(request):
    """
    Олимпиадуудын жагсаалт
    GET /api/olympiads/
    Query params:
    - limit: default 100
    - offset: default 0
    """
    limit = int(request.GET.get('limit', 100))
    offset = int(request.GET.get('offset', 0))

    olympiads = Olympiad.objects.select_related(
        'school_year', 'level', 'host'
    ).annotate(
        problem_count=models.Count('problems')
    ).filter(
        problem_count__gt=0
    ).order_by('-school_year__year', '-round', '-month')

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
            'school_year': olympiad.school_year.year if olympiad.school_year else None,
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
    """
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
            'school_year': olympiad.school_year.year if olympiad.school_year else None,
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
