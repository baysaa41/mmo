from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from datetime import datetime, timezone, timedelta
from olympiad.models import SchoolYear

from .models import Olympiad, Problem, Topic
from django.db.models import Q


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
        'next': next
    }
    return render(request, 'olympiad/problems/home.html', context=context)


@login_required
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


@login_required
def exam_view(request, olympiad_id):
    """
    Олимпиадын онлайн шалгалтын орчин.
    """
    olympiad = get_object_or_404(Olympiad, pk=olympiad_id)

    # Жишээ нь эхлэх, дуусах хугацааг шалгана
    now = timezone.now()
    if not (olympiad.start_time <= now <= olympiad.end_time):
        return render(request, "olympiad/exam/closed.html", {"olympiad": olympiad})

    problems = olympiad.problem_set.order_by('order')
    return render(request, "olympiad/exam/exam.html", {
        "olympiad": olympiad,
        "problems": problems,
    })


@login_required
def quiz_view(request, olympiad_id):
    """
    Богино асуулт/quiz төрлийн бодлогуудын жагсаалт.
    """
    olympiad = get_object_or_404(Olympiad, pk=olympiad_id)
    problems = olympiad.problem_set.filter(type="quiz").order_by('order')

    return render(request, "olympiad/quiz/home.html", {
        "olympiad": olympiad,
        "problems": problems,
    })


@login_required
def supplements_view(request, olympiad_id):
    """
    Supplement буюу нэмэлт материал (жишээ нь нөхөх тест, нэмэлт бодлого).
    """
    olympiad = get_object_or_404(Olympiad, pk=olympiad_id)
    supplements = olympiad.problem_set.filter(type="supplement").order_by('order')

    return render(request, "olympiad/supplements/home.html", {
        "olympiad": olympiad,
        "problems": supplements,
    })


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