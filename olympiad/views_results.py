from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, Max, Min
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime
from .models import Olympiad, Problem, Result, SchoolYear, ScoreSheet
from django.contrib.auth.models import User

from django.core.cache import cache



@login_required
def results_home(request):
    now = datetime.now(timezone.utc)
    school_year = SchoolYear.objects.filter(start__lt=now, end__gt=now).first()
    year_id = request.GET.get('year', school_year.id if school_year else None)
    year = SchoolYear.objects.filter(pk=year_id).first() if year_id else None

    prev = SchoolYear.objects.filter(pk=year.id - 1).first() if year else None
    next = SchoolYear.objects.filter(pk=year.id + 1).first() if year else None

    olympiads = Olympiad.objects.filter(is_open=True)

    # --- Бусад шүүлтүүрүүдийг шалгах ---
    name_query = request.GET.get('name', '').strip()
    round_param = request.GET.get('round', '')
    level_param = request.GET.get('level', '')

    # Хэрэв өөр шүүлтүүрүүд байхгүй бол зөвхөн жилээр шүүх
    if not (name_query or round_param or level_param):
        if year:
            olympiads = olympiads.filter(school_year=year)
    else:
        if name_query:
            olympiads = olympiads.filter(name__icontains=name_query)

        if round_param.isdigit():
            olympiads = olympiads.filter(round=int(round_param))

        if level_param.isdigit():
            olympiads = olympiads.filter(level_id=int(level_param))

    olympiads = olympiads.order_by('-school_year_id', 'round', 'level', 'name')

    context = {
        'olympiads': olympiads,
        'year': year,
        'prev': prev,
        'next': next,
    }
    return render(request, 'olympiad/results/home.html', context=context)


@login_required
def olympiad_results(request, olympiad_id):
    show_all = request.GET.get('all', False)
    olympiad = get_object_or_404(Olympiad, pk=olympiad_id)

    province_id = request.GET.get("p", "0").strip()
    zone_id = request.GET.get("z", "0").strip()
    page_number = request.GET.get("page", "1")

    # --- cache key үүсгэх ---
    cache_key = f"scores_{olympiad_id}_{province_id}_{zone_id}_{page_number}_{show_all}"
    score_data = cache.get(cache_key)

    if not score_data:
        # Queryset бэлтгэх
        if show_all:
            scoresheets = ScoreSheet.objects.filter(olympiad=olympiad)
        else:
            scoresheets = ScoreSheet.objects.filter(olympiad=olympiad, total__gt=0)

        problem_range = len(olympiad.problem_set.all()) + 1

        # --- шүүлтүүр ---
        if province_id != "0":
            scoresheets = scoresheets.filter(user__data__province_id=province_id)
            rank_field_a = "ranking_a_p"
            rank_field_b = "ranking_b_p"
            list_rank_field = "list_rank_p"
        elif zone_id != "0":
            scoresheets = scoresheets.filter(user__data__province__zone_id=zone_id)
            rank_field_a = "ranking_a_z"
            rank_field_b = "ranking_b_z"
            list_rank_field = "list_rank_z"
        else:
            rank_field_a = "ranking_a"
            rank_field_b = "ranking_b"
            list_rank_field = "list_rank"

        scoresheets = scoresheets.select_related("user__data__school__province", "school").order_by(list_rank_field)

        # --- dict болгон хувиргах ---
        score_data = []
        for sheet in scoresheets:
            try:
                province = (
                    (sheet.school.province.name if sheet.school and sheet.school.province else "")
                    or (sheet.user.data.province.name if sheet.user.data and sheet.user.data.province else "")
                )
                score_data.append({
                    "scoresheet_id": sheet.id,
                    "list_rank": getattr(sheet, list_rank_field),
                    "last_name": sheet.user.last_name,
                    "first_name": sheet.user.first_name,
                    "id": sheet.user.id,
                    "province": province,
                    "school": sheet.school,
                    "scores": [getattr(sheet, f"s{i}") for i in range(1, problem_range)],
                    "total": sheet.total,
                    "ranking_a": getattr(sheet, rank_field_a),
                    "ranking_b": getattr(sheet, rank_field_b),
                    "prizes": sheet.prizes,
                })
            except Exception as e:
                print("Алдаа:", e, sheet, sheet.user.id)

        # --- pagination ---
        paginator = Paginator(score_data, 50)
        page_obj = paginator.get_page(page_number)

        # зөвхөн page_obj хадгалах
        score_data = page_obj

        # cache-д хадгалах
        cache.set(cache_key, score_data, None)

    else:
        page_obj = score_data

    # --- хэрэглэгчийн оноо (динамикаар DB-с авах) ---
    user_score_data = None
    if request.user.is_authenticated:
        try:
            user_score_data = ScoreSheet.objects.get(olympiad=olympiad, user=request.user)
        except ScoreSheet.DoesNotExist:
            pass

    context = {
        "olympiad": olympiad,
        "page_title": "Нэгдсэн дүн",
        "score_data": page_obj,     # зөвхөн одоогийн хуудасны өгөгдөл
        "page_obj": page_obj,
        "user_score_data": user_score_data,
        "problem_range": range(1, len(olympiad.problem_set.all()) + 1),
        "selected_province": province_id,
        "selected_zone": zone_id,
    }
    return render(request, "olympiad/results/olympiad_id.html", context)

@login_required
def student_result_view(request, olympiad_id, contestant_id):
    results = Result.objects.filter(contestant_id=contestant_id, olympiad_id=olympiad_id).order_by('problem__order')
    contestant = User.objects.get(pk=contestant_id)
    olympiad = Olympiad.objects.get(pk=olympiad_id)
    username = contestant.last_name + ', ' + contestant.first_name
    return render(request, 'olympiad/results/student_result.html',
                  {'results': results, 'username': username, 'olympiad': olympiad})

@login_required
def problem_stats_view(request, problem_id):
    problem = get_object_or_404(Problem, pk=problem_id)
    results = Result.objects.filter(problem=problem, score__isnull=False)

    grouped = (results.values('score')
               .annotate(score_count=Count('score'))
               .order_by('score'))

    stats = results.aggregate(
        avg=Avg('score'),
        max=Max('score'),
        min=Min('score')
    )

        # --- ШИНЭ ХЭСЭГ: АЙМАГ БҮРЭЭР ДУНДАЖ ОНООГ ТООЦООЛОХ ---
    province_stats = (
        results.values('contestant__data__province')
        .annotate(average_score=Avg('score'))
        .exclude(contestant__data__province__isnull=True)   # 🔥 None-г хасах
        .order_by('contestant__data__province')
    )

    # Chart.js-д зориулж өгөгдлийг бэлдэх
    province_labels = [entry['contestant__data__province__name'] for entry in province_stats]
    province_avg_scores = [round(entry['average_score'], 2) for entry in province_stats]



    # --- Дараагийн болон өмнөх бодлогын id олох ---
    next_problem = (Problem.objects
                    .filter(olympiad=problem.olympiad, order__gt=problem.order)
                    .order_by('order')
                    .first())
    prev_problem = (Problem.objects
                    .filter(olympiad=problem.olympiad, order__lt=problem.order)
                    .order_by('-order')
                    .first())

    context = {
        'problem': problem,
        'count': results.count(),
        'results_grouped': grouped,
        'stats': stats,
        'next_problem': next_problem,
        'prev_problem': prev_problem,
        # Chart.js-д зориулсан шинэ өгөгдөл
        'province_labels': province_labels,
        'province_avg_scores': province_avg_scores,
    }
    print(context)
    return render(request, 'olympiad/stats/problem_stats.html', context)

