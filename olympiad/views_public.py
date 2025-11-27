from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from datetime import datetime, timezone, timedelta
from olympiad.models import SchoolYear, ScoreSheet, Olympiad, Problem, Topic
from django.db.models import Q, Count


def olympiads_home(request):
    now = datetime.now(timezone.utc)

    # Одоогийн идэвхтэй хичээлийн жилийг олох
    current_school_year = SchoolYear.objects.filter(start__lt=now, end__gt=now).first()

    # Шүүлтүүр хийх эцсийн хугацааг тооцоолох (одоогоос 7 хоногийн өмнөх)
    cutoff_date = now - timedelta(days=7)

    if current_school_year:
        # Хугацаа нь дуусаагүй бөгөөд одоогийн хичээлийн жилд хамаарах олимпиадуудыг шүүх
        olympiads = Olympiad.objects.filter(
            end_time__gte=cutoff_date,
            school_year=current_school_year
        ).order_by('start_time')
    else:
        # Идэвхтэй хичээлийн жил олдоогүй бол хоосон жагсаалт буцаах
        olympiads = Olympiad.objects.none()

    return render(request, 'olympiad/home.html', {'olympiads': olympiads, 'now': now})

def problems_home(request):
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
        if request.GET.get('year',False):
            olympiads = olympiads.filter(school_year=year)

        if name_query:
            olympiads = olympiads.filter(name__icontains=name_query)

        if round_param.isdigit():
            olympiads = olympiads.filter(round=int(round_param))

        if level_param.isdigit():
            olympiads = olympiads.filter(level_id=int(level_param))

    olympiads = olympiads.order_by('-school_year_id', 'round', 'name', 'level')

    context = {
        'olympiads': olympiads,
        'year': year,
        'prev': prev,
        'next': next
    }
    return render(request, 'olympiad/problems/home.html', context=context)


def problems_view(request, olympiad_id):
    """
    Олимпиадын бүх бодлогын жагсаалтыг харуулна.
    """
    olympiad = get_object_or_404(Olympiad, pk=olympiad_id)
    problems = olympiad.problem_set.order_by('order')

    context = {
        "olympiad": olympiad,
        "problems": problems,
    }
    return render(request, "olympiad/problems/list.html", context)

def problem_list_with_topics(request):
    # URL-аас ?q=... гэсэн хайлтын түлхүүр үгийг авах
    query = request.GET.get('q', '')

    # Анхдагч queryset-г тодорхойлох
    problems = Problem.objects.all().prefetch_related("topics")

    # Хэрэв хайлтын үг орж ирсэн бол queryset-г шүүх
    if query:
        problems = problems.filter(
            Q(statement__icontains=query) | # Бодлогын өгүүлбэрээс хайх
            Q(olympiad__name__icontains=query) | # Холбогдсон олимпиадын нэрээс хайх
            Q(topics__name__icontains=query)     # Холбогдсон сэдвүүдийн нэрээс хайх
        ).distinct() # Сэдвээр хайхад үүсэх давхардлыг арилгах

    all_topics = Topic.objects.all()

    return render(request, "olympiad/problems/problem_list_with_topics.html", {
        "problems": problems,
        "all_topics": all_topics,
        "query": query, # Хайлтын үгийг темплэйт рүү буцааж дамжуулах
    })

def olympiad_top_stats(request, olympiad_id):
    olympiad = get_object_or_404(Olympiad, id=olympiad_id)
    province_id = request.GET.get("p", "0").strip()
    zone_id = request.GET.get("z", "0").strip()

    scoresheets = ScoreSheet.objects.filter(olympiad=olympiad, total__gt=0)

    # --- аль ranking багана ашиглахыг шийдэх ---
    if province_id != "0":
        scoresheets = scoresheets.filter(user__data__province_id=province_id)
        rank_field = "ranking_a_p"
    elif zone_id != "0":
        scoresheets = scoresheets.filter(user__data__province__zone_id=zone_id)
        rank_field = "ranking_a_z"
    else:
        rank_field = "ranking_a"

    scoresheets = scoresheets.order_by(rank_field)

    if olympiad.level.id in [2,3,4,5]:
        # Эхний 50 ба эхний 30-г тасалж авах
        top50 = scoresheets.filter(**{f"{rank_field}__lte": 50})
        top30 = scoresheets.filter(**{f"{rank_field}__lte": 30})
        top_name_50 = '50'
        top_name_30 = '30'
    else:
        top50 = scoresheets.filter(**{f"{rank_field}__lte": 30})
        top30 = scoresheets.filter(**{f"{rank_field}__lte": 10})
        top_name_50 = '30'
        top_name_30 = '10'

    # --- Нэмэлтээр нийт тоог авах ---
    top50_count = top50.count()
    top30_count = top30.count()

    # Статистикууд
    top50_by_school = top50.values("school__name").annotate(count=Count("id")).order_by("-count")
    top30_by_province = top30.values("user__data__province__name").annotate(count=Count("id")).order_by("-count")
    top30_by_zone = top30.values("user__data__province__zone__name").annotate(count=Count("id")).order_by("-count")

    # Нийлбэр онооны тархалт (гистограмм)
    score_distribution = scoresheets.values('total').annotate(count=Count('id')).order_by('total')

    # Chart.js-д зориулсан өгөгдөл бэлтгэх
    score_labels = [str(int(item['total'])) for item in score_distribution]
    score_counts = [item['count'] for item in score_distribution]

    context = {
        "olympiad": olympiad,
        "top50_by_school": top50_by_school,
        "top30_by_province": top30_by_province,
        "top30_by_zone": top30_by_zone,
        "selected_province": province_id,
        "selected_zone": zone_id,
        "rank_field": rank_field,
        "top50_count": top50_count,
        "top30_count": top30_count,
        "top_name_50": top_name_50,
        "top_name_30": top_name_30,
        "score_labels": score_labels,
        "score_counts": score_counts,
    }
    return render(request, "olympiad/olympiad_top_stats.html", context)