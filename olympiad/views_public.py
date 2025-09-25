from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from datetime import datetime, timezone, timedelta
from olympiad.models import SchoolYear

from .models import Olympiad, Problem, Topic


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
    mode = request.GET.get('mode', 0)
    school_year = SchoolYear.objects.filter(start__lt=now, end__gt=now).first()
    id = request.GET.get('year', school_year.id)
    year = SchoolYear.objects.filter(pk=id).first()
    prev = SchoolYear.objects.filter(pk=year.id - 1).first()
    next = SchoolYear.objects.filter(pk=year.id + 1).first()

    olympiads = Olympiad.objects.filter(is_open=True).order_by('-school_year_id', 'name', 'level')

    if id:
        olympiads = olympiads.filter(school_year=year)

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
    problems = Problem.objects.all().prefetch_related("topics")
    all_topics = Topic.objects.all()   # 👈 энд бүх topics авч дамжуулна
    return render(request, "olympiad/problems/problem_list_with_topics.html", {
        "problems": problems,
        "all_topics": all_topics,
    })