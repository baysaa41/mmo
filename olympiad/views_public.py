from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
from datetime import datetime, timezone, timedelta
from olympiad.models import SchoolYear, ScoreSheet, Olympiad, Problem, Topic, RoundGuideline, Award, OlympiadTimeline
from olympiad.utils.round2_quota import compute_school_quota_table
from olympiad.utils.round3_quota import compute_district_quota_table, get_capital_districts
from accounts.models import Province
from django.db.models import Q, Count
from django.core.cache import cache


def _round1_student_status(user):
    """Сурагч сургуулийн олимпиад (I даваа)-д бүртгэлтэй эсэхийг тодорхойлно."""
    meta = getattr(user, 'data', None)
    school = meta.school if meta else None
    if not school:
        return {'has_school': False, 'province': meta.province if meta else None}
    return {'has_school': True, 'school': school, 'registered': meta.is_school_registered()}


def _imo_student_status(user, year):
    """IMO сорилгод оролцохын тулд Улсын олимпиадын F ангилалд эрх авсан байх шаардлагатай."""
    qualified = Award.objects.filter(
        contestant=user,
        olympiad__school_year=year,
        olympiad__level__name__startswith='F',
        place__startswith='Улсын эрх',
    ).exists()
    return {'qualified': qualified}


def _egmo_student_status(user, year):
    """EGMO сорилгод оролцохын тулд Аймаг/Дүүргийн олимпиадын E эсвэл F ангилалд ядаж 1 оноо авсан эмэгтэй сурагч байх шаардлагатай."""
    meta = getattr(user, 'data', None)
    is_female = bool(meta and meta.gender and meta.gender.strip().upper().startswith('ЭМ'))
    qualified = is_female and ScoreSheet.objects.filter(
        user=user,
        olympiad__round=2,
        olympiad__school_year=year,
        is_official=True,
        total__gte=1,
    ).filter(
        Q(olympiad__level__name__startswith='E') | Q(olympiad__level__name__startswith='F')
    ).exists()
    return {'qualified': qualified, 'is_female': is_female}


def _round_student_status(user, year, prev_round, place_prefix):
    """Сурагч өмнөх давааны шат-аас шалгарсан, тухайн давааны олимпиадад бүртгэлтэй эсэхийг тодорхойлно."""
    qualified = Award.objects.filter(
        contestant=user, olympiad__round=prev_round, olympiad__school_year=year, place__startswith=place_prefix
    ).exists()
    registered = Olympiad.objects.filter(
        round=prev_round + 1, school_year=year, group__isnull=False, group__user=user
    ).exists()
    return {'qualified': qualified, 'registered': registered}


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


def get_capital_quota_tables(selected_year, force_update=False):
    """Тухайн хичээлийн жилийн нийслэлийн round=3 дүүргийн квотын хүснэгтүүдийг
    (ангилал бүрээр, D/E/F/S/T) буцаана — round3_district_quota_view (дэлгэрэнгүй
    "Хотын эрхийн дэвтэр") болон round_guideline_view (round=3 хуудасны товч
    хүснэгт) хоёулаа ашигладаг тул кэштэй хамт нэг дор."""
    cache_key = f"round3_district_quota_{selected_year.id}"
    cached = None if force_update else cache.get(cache_key)
    if cached is not None:
        return cached

    quota_tables = []
    capital_olympiads = Olympiad.objects.filter(
        round=3, school_year=selected_year, name__icontains='нийслэл'
    ).select_related('level').order_by('level_id')

    for o in capital_olympiads:
        if not o.level:
            continue
        is_teacher_category = o.level.name.startswith('S') or o.level.name.startswith('T')
        table = compute_district_quota_table(o.level, selected_year, is_teacher_category)
        if table:
            quota_tables.append({'level': o.level, **table})

    # Хугацаагүй хадгална: зөвхөн generate_scoresheets команд (cache.clear() дуудна)
    # эсвэл ?clean=1-ээр хүчээр шинэчлэгдэх үед л өөрчлөгдөнө.
    cache.set(cache_key, quota_tables, None)
    return quota_tables


def round_guideline_view(request, round):
    now = datetime.now(timezone.utc).date()
    active_year = SchoolYear.objects.filter(start__lte=now, end__gte=now).first()
    year_id = request.GET.get('year', active_year.id if active_year else None)
    selected_year = SchoolYear.objects.filter(pk=year_id).first() if year_id else None

    guideline = None
    if selected_year:
        guideline = RoundGuideline.objects.filter(round=round, school_year=selected_year).first()
    if not guideline:
        # Тухайн жилд удирдамж оруулаагүй бол хамгийн сүүлд оруулсныг харуулна
        guideline = RoundGuideline.objects.filter(round=round).order_by('-school_year_id').first()

    # round 5/6/7 (IMO/EGMO/APMO) нь Olympiad.round талбартай шууд нийцдэггүй
    # (өгөгдлийн санд round=0/4/6/7-д тархсан байдаг тул нэрээр нь шүүнэ)
    name_filter_map = {5: 'IMO', 6: 'EGMO', 7: 'APMO'}
    olympiads = []
    if selected_year:
        if round in name_filter_map:
            olympiads = Olympiad.objects.filter(
                is_open=True, name__icontains=name_filter_map[round], school_year=selected_year
            ).order_by('start_time')
        else:
            olympiads = Olympiad.objects.filter(
                is_open=True, round=round, school_year=selected_year
            ).order_by('level_id')

    prev_year = SchoolYear.objects.filter(pk=selected_year.id - 1).first() if selected_year else None
    next_year = SchoolYear.objects.filter(pk=selected_year.id + 1).first() if selected_year else None

    student_status = None
    if request.user.is_authenticated and selected_year:
        olympiads = list(olympiads)
        for o in olympiads:
            o.access_status = o.get_access_status(request.user)

        if round == 1:
            student_status = _round1_student_status(request.user)
        elif round == 2:
            student_status = _round_student_status(request.user, selected_year, prev_round=1, place_prefix='2.1')
        elif round == 3:
            student_status = _round_student_status(request.user, selected_year, prev_round=2, place_prefix='2.2 эрх')
        elif round == 5:
            student_status = _imo_student_status(request.user, selected_year)
        elif round == 6:
            student_status = _egmo_student_status(request.user, selected_year)

    capital_quota_pivot = None
    guideline_content_before = guideline.content if guideline else None
    guideline_content_after = None
    if round == 3 and selected_year:
        # "Хотын эрхийн дэвтэр"-ийг удирдамжийн "Бүсийн эрх"-ийн хүснэгтийн ард, харин
        # "Улсын олимпиадын эрх олгох" хэсгийн өмнө оруулахын тулд удирдамжийн HTML-г
        # тэр хэсгийн эхлэлээр таслана. Тэмдэглэгээ олдохгүй бол бүх агуулгыг өмнө нь
        # үзүүлнэ.
        if guideline and guideline.content:
            marker = '<p><strong>Улсын олимпиадын эрх олгох'
            split_idx = guideline.content.find(marker)
            if split_idx != -1:
                guideline_content_before = guideline.content[:split_idx]
                guideline_content_after = guideline.content[split_idx:]

        quota_tables = get_capital_quota_tables(selected_year)
        if quota_tables:
            levels = [qt['level'] for qt in quota_tables]
            district_rows = []
            for d in get_capital_districts():
                values = []
                for qt in quota_tables:
                    match = next((r for r in qt['districts_data'] if r['district'].id == d.id), None)
                    values.append(match['total_quota'] if match else 0)
                district_rows.append({'district': d, 'values': values, 'row_total': sum(values)})
            totals = [qt['total_quota'] for qt in quota_tables]
            capital_quota_pivot = {
                'levels': levels,
                'district_rows': district_rows,
                'totals': totals,
                'grand_total': sum(totals),
            }

    context = {
        'round': round,
        'round_name': dict(RoundGuideline.ROUND_CHOICES).get(round, ''),
        'guideline': guideline,
        'olympiads': olympiads,
        'year': selected_year,
        'prev': prev_year,
        'next': next_year,
        'student_status': student_status,
        'capital_quota_pivot': capital_quota_pivot,
        'guideline_content_before': guideline_content_before,
        'guideline_content_after': guideline_content_after,
    }
    return render(request, 'olympiad/round_detail.html', context)


def round2_school_quota_view(request):
    """Аймаг/дүүргийн олимпиад (round=2): сургуулиудын эрхийн тооцоог аймаг/дүүрэг,
    ангилал сонгож харах нийтийн хуудас."""
    now = datetime.now(timezone.utc).date()
    active_year = SchoolYear.objects.filter(start__lte=now, end__gte=now).first()
    year_id = request.GET.get('year', active_year.id if active_year else None)
    selected_year = SchoolYear.objects.filter(pk=year_id).first() if year_id else None

    prev_year = SchoolYear.objects.filter(pk=selected_year.id - 1).first() if selected_year else None
    next_year = SchoolYear.objects.filter(pk=selected_year.id + 1).first() if selected_year else None

    all_provinces = Province.objects.order_by('name')
    selected_province = None
    province_id = request.GET.get('province')
    if province_id:
        selected_province = Province.objects.filter(pk=province_id).first()

    all_categories = []
    selected_category_id = None
    quota_tables = []
    if selected_year:
        student_olympiads_qs = Olympiad.objects.filter(
            round=2, school_year=selected_year
        ).exclude(
            Q(level__name__startswith='S') | Q(level__name__startswith='T')
        ).select_related('level').order_by('level_id')
        all_categories = [o.level for o in student_olympiads_qs]

        category_id = request.GET.get('category')
        if category_id:
            try:
                selected_category_id = int(category_id)
            except (TypeError, ValueError):
                selected_category_id = None

        if selected_province:
            olympiads_to_compute = student_olympiads_qs
            if selected_category_id:
                olympiads_to_compute = olympiads_to_compute.filter(level_id=selected_category_id)
            for o in olympiads_to_compute:
                table = compute_school_quota_table(selected_province, o)
                if table:
                    quota_tables.append({'province': selected_province, 'round2_olympiad': o, **table})

    context = {
        'year': selected_year,
        'prev': prev_year,
        'next': next_year,
        'all_provinces': all_provinces,
        'selected_province': selected_province,
        'all_categories': all_categories,
        'selected_category_id': selected_category_id,
        'quota_tables': quota_tables,
    }
    return render(request, 'olympiad/round2_quota.html', context)


def round2_quota_summary_view(request):
    """Аймаг/дүүрэг бүрийн 2-р даваанд нэмэгдэх (жагсаалтаар) эрхийн нийлбэрийг нэг дор
    харуулах нэгдсэн тайлан (Квотын дэвтэр)."""
    now = datetime.now(timezone.utc).date()
    active_year = SchoolYear.objects.filter(start__lte=now, end__gte=now).first()
    year_id = request.GET.get('year', active_year.id if active_year else None)
    selected_year = SchoolYear.objects.filter(pk=year_id).first() if year_id else None

    prev_year = SchoolYear.objects.filter(pk=selected_year.id - 1).first() if selected_year else None
    next_year = SchoolYear.objects.filter(pk=selected_year.id + 1).first() if selected_year else None

    levels = []
    aimags = []
    duuregs = []
    grand = {'schools': 0, 'base': 0, 'additional': 0, 'quota': 0}
    max_aimag = 0
    max_duureg = 0

    if selected_year:
        force_update = request.GET.get('clean', '0') == '1'
        cache_key = f"round2_quota_summary_{selected_year.id}"
        cached = None if force_update else cache.get(cache_key)

        if cached:
            levels, aimags, duuregs, grand, max_aimag, max_duureg = cached
        else:
            student_olympiads_qs = Olympiad.objects.filter(
                round=2, school_year=selected_year
            ).exclude(
                Q(level__name__startswith='S') | Q(level__name__startswith='T')
            ).select_related('level').order_by('level_id')
            levels = [o.level for o in student_olympiads_qs]

            summary = []
            for province in Province.objects.order_by('id'):
                entry = {
                    'province': province,
                    'is_aimag': province.id <= 21,
                    'levels': {},
                    'base_total': 0,
                    'additional_total': 0,
                    'quota_total': 0,
                    'school_count': 0,
                    'configured': False,
                }
                for o in student_olympiads_qs:
                    table = compute_school_quota_table(province, o)
                    if table is None:
                        entry['levels'][o.level_id] = None
                        continue
                    entry['configured'] = True
                    entry['levels'][o.level_id] = table['total_additional']
                    entry['base_total'] += table['total_base']
                    entry['additional_total'] += table['total_additional']
                    entry['quota_total'] += table['total_quota']
                    entry['school_count'] = max(entry['school_count'], len(table['schools_data']))
                summary.append(entry)

            aimags = sorted([e for e in summary if e['is_aimag']], key=lambda e: -e['additional_total'])
            duuregs = sorted([e for e in summary if not e['is_aimag']], key=lambda e: -e['additional_total'])

            grand = {
                'count': len(aimags) + len(duuregs),
                'schools': sum(e['school_count'] for e in summary),
                'base': sum(e['base_total'] for e in summary),
                'additional': sum(e['additional_total'] for e in summary),
                'quota': sum(e['quota_total'] for e in summary),
            }
            max_aimag = max([e['additional_total'] for e in aimags], default=0) or 1
            max_duureg = max([e['additional_total'] for e in duuregs], default=0) or 1

            # Хугацаагүй хадгална: энэ өгөгдөл зөвхөн generate_scoresheets команд (cache.clear()
            # дуудна) эсвэл ?clean=1-ээр хүчээр шинэчлэгдэх үед л өөрчлөгдөнө.
            cache.set(cache_key, (levels, aimags, duuregs, grand, max_aimag, max_duureg), None)

    context = {
        'year': selected_year,
        'prev': prev_year,
        'next': next_year,
        'levels': levels,
        'aimags': aimags,
        'duuregs': duuregs,
        'grand': grand,
        'max_aimag': max_aimag,
        'max_duureg': max_duureg,
    }
    return render(request, 'olympiad/round2_quota_summary.html', context)


def round3_district_quota_view(request):
    """Нийслэлийн олимпиад (round=3, Хотын эрх): дүүрэг тус бүрийн эрхийн тооцоог
    ангилал бүрээр (D, E, F, S, T) нэг дор харах нийтийн хуудас ("Хотын эрхийн дэвтэр")."""
    now = datetime.now(timezone.utc).date()
    active_year = SchoolYear.objects.filter(start__lte=now, end__gte=now).first()
    year_id = request.GET.get('year', active_year.id if active_year else None)
    selected_year = SchoolYear.objects.filter(pk=year_id).first() if year_id else None

    prev_year = SchoolYear.objects.filter(pk=selected_year.id - 1).first() if selected_year else None
    next_year = SchoolYear.objects.filter(pk=selected_year.id + 1).first() if selected_year else None

    quota_tables = []
    if selected_year:
        force_update = request.GET.get('clean', '0') == '1'
        quota_tables = get_capital_quota_tables(selected_year, force_update=force_update)

    context = {
        'year': selected_year,
        'prev': prev_year,
        'next': next_year,
        'quota_tables': quota_tables,
    }
    return render(request, 'olympiad/round3_district_quota.html', context)


def problems_home(request):
    now = datetime.now(timezone.utc)
    school_year = SchoolYear.objects.filter(start__lt=now, end__gt=now).first()
    year_id = request.GET.get('year', school_year.id if school_year else None)
    year = SchoolYear.objects.filter(pk=year_id).first() if year_id else None

    prev = SchoolYear.objects.filter(pk=year.id - 1).first() if year else None
    next = SchoolYear.objects.filter(pk=year.id + 1).first() if year else None

    olympiads = Olympiad.objects.filter(is_open=True)

    # Нууц бодлоготой олимпиадыг зөвхөн эрх бүхий хэрэглэгчдэд харуулах
    user = request.user
    if user.is_authenticated and user.is_staff:
        pass  # staff бүгдийг харна
    elif user.is_authenticated:
        user_group_ids = user.groups.values_list('id', flat=True)
        olympiads = olympiads.filter(
            Q(is_problems_confidential=False) |
            Q(is_problems_confidential=True, group__in=user_group_ids)
        )
    else:
        olympiads = olympiads.filter(is_problems_confidential=False)

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

    if olympiad.is_problems_confidential:
        user = request.user
        is_in_group = (
            user.is_authenticated
            and olympiad.group
            and user.groups.filter(pk=olympiad.group.pk).exists()
        )
        if not (user.is_authenticated and (user.is_staff or is_in_group)):
            return HttpResponseForbidden("Энэ олимпиадын бодлогыг харах эрх байхгүй байна.")

    problems = olympiad.problem_set.prefetch_related('coordinators').order_by('order')

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

    # Нууц бодлоготой олимпиадын бодлогыг шүүх
    user = request.user
    if not (user.is_authenticated and user.is_staff):
        if user.is_authenticated:
            user_group_ids = user.groups.values_list('id', flat=True)
            problems = problems.filter(
                Q(olympiad__is_problems_confidential=False) |
                Q(olympiad__is_problems_confidential=True, olympiad__group__in=user_group_ids)
            )
        else:
            problems = problems.filter(olympiad__is_problems_confidential=False)

    # Хэрэв хайлтын үг орж ирсэн бол queryset-г шүүх
    if query:
        problems = problems.filter(
            Q(statement__icontains=query) | # Бодлогын өгүүлбэрээс хайх
            Q(olympiad__name__icontains=query) | # Холбогдсон олимпиадын нэрээс хайх
            Q(topics__name__icontains=query)     # Холбогдсон сэдвүүдийн нэрээс хайх
        ).distinct() # Сэдвээр хайхад үүсэх давхардлыг арилгах

    all_topics = Topic.objects.all()

    paginator = Paginator(problems, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "olympiad/problems/problem_list_with_topics.html", {
        "problems": page_obj,
        "all_topics": all_topics,
        "query": query, # Хайлтын үгийг темплэйт рүү буцааж дамжуулах
    })

def olympiad_top_stats(request, olympiad_id):
    olympiad = get_object_or_404(Olympiad, id=olympiad_id)
    province_id = request.GET.get("p", "0").strip()
    zone_id = request.GET.get("z", "0").strip()

    scoresheets = ScoreSheet.objects.filter(olympiad=olympiad)

    # --- аль ranking багана ашиглахыг шийдэх ---
    if province_id != "0":
        scoresheets = scoresheets.filter(school__province_id=province_id)
        rank_field = "ranking_a_p"
    elif zone_id != "0":
        scoresheets = scoresheets.filter(school__province__zone_id=zone_id)
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
    top30_by_province = top30.values("school__province__name").annotate(count=Count("id")).order_by("-count")
    top30_by_zone = top30.values("school__province__zone__name").annotate(count=Count("id")).order_by("-count")

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


def olympiad_timeline_view(request):
    """ММО-ийн Улсын олимпиадуудын түүхэн жагсаалт (imo-official.org/editions
    хуудастай төстэй): дугаар, огноо, байршил, тайлбар, оролцогчдын тоо.

    OlympiadTimeline нь Olympiad-аас тооцоологддоггүй бие даасан хүснэгт —
    staff зөвхөн үүнийг л (Django admin-аар) засварлаж шинэ мөр нэмнэ.
    """
    rows = OlympiadTimeline.objects.select_related('school_year', 'host').all()
    next_edition = (rows[0].number + 1) if rows else 1
    return render(request, 'olympiad/timeline.html', {
        'rows': rows,
        'next_edition': next_edition,
        'next_edition_name': f'ММО-{next_edition}-р олимпиад',
    })