from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, Max, Min
from django.core.paginator import Paginator
from datetime import datetime, timezone
from .models import Olympiad, Problem, Result, SchoolYear, ScoreSheet
from accounts.models import Province
from schools.models import School
from django.contrib.auth.models import User
import pandas as pd
import numpy as np
import re

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
    return render(request, 'olympiad/results/home.html', context=context)


@login_required
def olympiad_results(request, olympiad_id):
    show_all = request.GET.get('all', False)
    olympiad = get_object_or_404(Olympiad, pk=olympiad_id)

    province_id = request.GET.get("p", "0").strip()
    zone_id = request.GET.get("z", "0").strip()
    page_number = request.GET.get("page", "1")

    # --- 1. 'update=1' флагийг шалгах ---
    force_update = request.GET.get('clean', '0') == '1'

    # --- cache key үүсгэх ---
    cache_key = f"scores_{olympiad_id}_{province_id}_{zone_id}_{page_number}_{show_all}"

    score_data = None # Анхны утгыг None болгох

    # --- 2. 'force_update' ХИЙГЭЭГҮЙ үед л cache-с унших ---
    if not force_update:
        score_data = cache.get(cache_key)

    # --- 3. Cache-д байхгүй ЭСВЭЛ 'force_update=1' үед ---
    if not score_data:

        # Хэрэв force_update хийсэн бол мэдээлэх (заавал биш)
        if force_update:
            print(f"CACHE FORCED REFRESH: {cache_key}")

        # Queryset бэлтгэх
        if show_all:
            scoresheets = ScoreSheet.objects.filter(olympiad=olympiad)
        else:
            # 0 оноотойг харуулахаар зассан хувилбар (өмнөх асуултын дагуу)
            scoresheets = ScoreSheet.objects.filter(olympiad=olympiad)

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
        score_data_list = [] # Нэрийг нь 'score_data' -аас 'score_data_list' болгов
        for sheet in scoresheets:
            try:
                province = (
                    (sheet.school.province.name if sheet.school and sheet.school.province else "")
                    or (sheet.user.data.province.name if sheet.user.data and sheet.user.data.province else "")
                )
                score_data_list.append({
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
        paginator = Paginator(score_data_list, 50) # 'score_data' биш 'score_data_list'-г ашиглана
        page_obj = paginator.get_page(page_number)

        # зөвхөн page_obj хадгалах
        score_data = page_obj

        # --- 4. Cache-д шинээр дарж бичих ---
        # 'None' гэвэл cache хэзээ ч expire болохгүй.
        # 3600 (1 цаг) гэх мэт хугацаа тавих нь илүү зохимжтой.
        cache.set(cache_key, score_data, 3600) # 1 цаг (эсвэл None)

    else:
        # Cache-с олдсон (учир нь force_update=False байсан)
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
        "score_data": page_obj,
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
        results.values('contestant__data__province', 'contestant__data__province__name')
        .annotate(average_score=Avg('score'))
        .exclude(contestant__data__province__isnull=True)
        .order_by('contestant__data__province')
    )

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
    # print(context)
    return render(request, 'olympiad/stats/problem_stats.html', context)


def olympiad_group_result_view(request, group_id):
    try:
        olympiad_group = OlympiadGroup.objects.get(pk=group_id)
    except OlympiadGroup.DoesNotExist:
        return render(request, 'olympiad/results/no_olympiad.html')
    except Exception as e:
        return render(request, 'messages/../templates/schools/error.html', {'message': str(e)})
    olympiads = olympiad_group.olympiads.all().order_by('id')
    answers = Result.objects.filter(olympiad__in=olympiads)
    title = 'Нэгдсэн дүн'

    if answers.count() == 0:
        context = {
            'df': '',
            'pivot': '',
            'quiz': '',
            'title': 'Оролцсон сурагч байхгүй.',
        }
        return render(request, 'olympiad/pandas_results_view.html', context)

    if olympiad_group.group_id:
        users = olympiad_group.group.user_set.all()
    else:
        users = User.objects.all()
    answers_df = read_frame(answers, fieldnames=['contestant_id', 'problem_id', 'score'], verbose=False)
    users_df = read_frame(users, fieldnames=['last_name', 'first_name', 'id', 'data__school'], verbose=False)
    answers_df['score'] = answers_df['score'].fillna(0)
    pivot = answers_df.pivot_table(index='contestant_id', columns='problem_id', values='score')
    pivot["Дүн"] = pivot.sum(axis=1)
    results = users_df.merge(pivot, left_on='id', right_on='contestant_id', how='inner')
    results.sort_values(by='Дүн', ascending=False, inplace=True)
    results['id'].fillna(0).astype(int)
    results['id'] = results['id'].apply(lambda x: "{id:.0f}".format(id=x))
    results.rename(columns={
        'id': 'ID',
        'first_name': 'Нэр',
        'last_name': 'Овог',
        'data__school': 'Cургууль',
        'link': '<i class="fas fa-expand-wide"></i>',
    }, inplace=True)
    results.index = np.arange(1, results.__len__() + 1)

    pd.set_option('colheader_justify', 'center')

    num = 0
    for olympiad in olympiads:
        num = num + 1
        for item in olympiad.problem_set.all().order_by('order'):
            results = results.rename(columns={item.id: '№' + str(num) + '.' + str(item.order)})

    # print(results.columns)
    columns1 = list(results.columns[:4])
    columns2 = sorted(results.columns[4:-1])
    columns3 = list(results.columns[-1:])
    # columns1.update(columns2)
    # print(columns1, columns2, columns3)
    results = results.reindex(columns1 + columns2 + columns3, axis=1)

    context = {
        'df': results.to_html(classes='table table-bordered table-hover', border=3, na_rep="", escape=False),
        'pivot': results.to_html(classes='table table-bordered table-hover', na_rep="", escape=False),
        'quiz': {
            'name': olympiad_group.name,
        },
        'title': title,
    }
    return render(request, 'olympiad/pandas_results_view.html', context)

@staff_member_required
def answers_view(request, olympiad_id):
    pid = int(request.GET.get('p', 0))
    sid = int(request.GET.get('s', 0))
    school = None
    context_data = ''

    try:
        olympiad = Olympiad.objects.get(pk=olympiad_id)
    except Olympiad.DoesNotExist:
        return render(request, 'olympiad/results/no_olympiad.html')

    provinces = Province.objects.all().order_by('name')
    schools = School.objects.filter(province_id=pid).order_by('name') if pid > 0 else School.objects.none()

    if sid > 0:
        try:
            school = School.objects.get(pk=sid)
        except School.DoesNotExist:
            school = None

        results = Result.objects.filter(olympiad_id=olympiad_id, contestant__data__school_id=sid)

        if results.exists():
            rows = list(results.values_list('contestant_id', 'problem_id', 'answer'))
            data = pd.DataFrame(rows, columns=['contestant_id', 'problem_id', 'answer'])

            # --- ӨӨРЧЛӨЛТ 1: fill_value=0 болон .astype(int)-г устгах ---
            # Ингэснээр NULL утгууд нь DataFrame дотор NaN (Not a Number) болж хадгалагдана.
            results_df = pd.pivot_table(data, index='contestant_id', columns='problem_id', values='answer', aggfunc='sum')

            problem_ids = results_df.columns.values
            problem_orders = {p.id: f'№{p.order:02d}' for p in Problem.objects.filter(id__in=problem_ids)}
            results_df.columns = [problem_orders.get(col, 'Unknown') for col in results_df.columns]
            results_df = results_df[sorted(results_df.columns)]

            contestant_ids = list(results_df.index)
            contestants_data = User.objects.filter(pk__in=contestant_ids).values('id', 'last_name', 'first_name')
            user_df = pd.DataFrame(list(contestants_data))
            user_df.columns = ['ID', 'Овог', 'Нэр']

            user_results_df = pd.merge(user_df, results_df, left_on='ID', right_index=True, how='left')
            sorted_df = user_results_df.sort_values(by=['Овог', 'Нэр']).drop(columns=['ID'])
            sorted_df.index = np.arange(1, len(sorted_df) + 1)

            # --- ШИНЭЧИЛСЭН ХЭСЭГ ---
            # 1. Тоон утгатай багануудын жагсаалтыг үүсгэх (нэр нь '№'-ээр эхэлсэн)
            numeric_columns = [col for col in sorted_df.columns if str(col).startswith('№')]

            # 2. Форматчилах функцээ тодорхойлох
            formatter = lambda val: '{:.0f}'.format(val) if val > 0 else '---'

            # 3. Зөвхөн тоон багануудад ('subset') форматчилах үйлдлийг хийх
            styled_df = (sorted_df.style
                                  .format(formatter, subset=numeric_columns, na_rep="-")
                                  .set_table_attributes('class="table table-bordered table-hover"'))
            context_data = styled_df.to_html()

             # --- ОНОШЛОГОО 1: pivot_table-ийн дараах үр дүнг шалгах ---
            results_df = pd.pivot_table(data, index='contestant_id', columns='problem_id', values='answer', aggfunc='sum')

    # Гарчиг болон бусад мэдээллийг бэлтгэх
    name = f"{olympiad.name}, {olympiad.level.name} ангилал"
    title = olympiad.name
    if school:
        title = school.name
    elif pid > 0:
        try:
            province = Province.objects.get(pk=pid)
            title = province.name
        except Province.DoesNotExist:
            pass

    context = {
        'title': f"{title} - Үр дүн",
        'name': name,
        'data': re.sub(r'&nbsp;</th>', r'№</th>', context_data),
        'school': school,
        'provinces': provinces,
        'schools': schools,
        'selected_pid': pid,
        'selected_sid': sid,
        'olympiad_id': olympiad_id,
    }

    return render(request, 'olympiad/results/answers.html', context)


#summary

# views_results.py файлд нэмнэ үү
# (Энэ файл дахь бусад import-ууд (pandas, User, School г.м)
# хэдийнэ байгаа тул шинээр import хийх шаардлагагүй)

# views_results.py файл дахь функцээ энэ кодоор солино уу

@login_required
def province_summary_view(request, olympiad_id):
    pid = int(request.GET.get('p', 0))
    sid = int(request.GET.get('s', 0))

    school_summaries = [] # Тойм хадгалах лист

    try:
        olympiad = Olympiad.objects.get(pk=olympiad_id)
    except Olympiad.DoesNotExist:
        return render(request, 'olympiad/results/no_olympiad.html')

    provinces = Province.objects.all().order_by('name')
    schools = School.objects.filter(province_id=pid).order_by('name') if pid > 0 else School.objects.none()

    province = None
    if pid > 0:
        try:
            province = Province.objects.get(pk=pid)
        except Province.DoesNotExist:
            pass

        # Тухайн аймгийн *бүх* сургуулийг багшийн мэдээлэлтэй нь хамт авна
        schools_in_province = (School.objects
                               .filter(province_id=pid)
                               .select_related('user', 'user__data')
                               .order_by('name'))

        for school in schools_in_province:
            # Тухайн сургуулийн үр дүнг шүүнэ
            results = Result.objects.filter(olympiad_id=olympiad_id, contestant__data__school_id=school.id)

            # Сурагчдын ID-г ялгаатайгаар авна
            contestant_ids = results.values_list('contestant_id', flat=True).distinct()
            total_count = contestant_ids.count()

            # --- ӨӨРЧЛӨГДСӨН ЛОГИК ---

            empty_row_count = 0
            sample_data_html = ""

            if total_count > 0:
                # 1. "Хоосон мөр"-ийн тоо (Зөвхөн оролцогч > 0 үед тоолно)
                positive_scorers_count = results.filter(score__gt=0).values_list('contestant_id', flat=True).distinct().count()
                empty_row_count = total_count - positive_scorers_count

                # 2. 5 сурагчийн түүвэр (Зөвхөн оролцогч > 0 үед тоолно)
                sample_contestant_ids = list(contestant_ids[:5])

                sample_results = results.filter(contestant_id__in=sample_contestant_ids)
                rows = list(sample_results.values_list('contestant_id', 'problem_id', 'answer'))
                data = pd.DataFrame(rows, columns=['contestant_id', 'problem_id', 'answer'])

                results_df = pd.pivot_table(data, index='contestant_id', columns='problem_id', values='answer', aggfunc='sum')

                problem_ids = results_df.columns.values
                problem_orders = {p.id: f'№{p.order:02d}' for p in Problem.objects.filter(id__in=problem_ids, olympiad=olympiad)}
                results_df.columns = [problem_orders.get(col, 'Unknown') for col in results_df.columns]
                results_df = results_df[sorted(results_df.columns)]

                contestants_data = User.objects.filter(pk__in=sample_contestant_ids).values('id', 'last_name', 'first_name')
                user_df = pd.DataFrame(list(contestants_data))
                user_df.columns = ['ID', 'Овог', 'Нэр']

                user_results_df = pd.merge(user_df, results_df, left_on='ID', right_index=True, how='left')
                sorted_df = user_results_df.sort_values(by=['Овог', 'Нэр']).drop(columns=['ID'])
                sorted_df.index = np.arange(1, len(sorted_df) + 1)

                numeric_columns = [col for col in sorted_df.columns if str(col).startswith('№')]
                formatter = lambda val: '{:.0f}'.format(val) if val > 0 else '---'

                styled_df = (sorted_df.style
                                      .format(formatter, subset=numeric_columns, na_rep="-")
                                      .set_table_attributes('class="table table-bordered table-hover"'))
                sample_data_html = re.sub(r'&nbsp;</th>', r'№</th>', styled_df.to_html())

            else:
                # Оролцогч байхгүй үед харуулах зурвас
                sample_data_html = "<p class='text-muted fst-italic'>Энэ олимпиадад оролцсон сурагч олдсонгүй.</p>"

            # --- ӨӨРЧЛӨЛТ ДУУСАВ ---

            # Сургуулийг *үргэлж* жагсаалтад нэмнэ
            school_summaries.append({
                'school': school,
                'total_count': total_count,
                'empty_row_count': empty_row_count,
                'sample_data_html': sample_data_html,
            })

    # Контекст болон render хэсэг хэвээрээ
    context = {
        'title': f"{province.name if province else 'Аймгийн'} тойм" if pid > 0 else "Аймгийн тойм",
        'name': f"{olympiad.name}, {olympiad.level.name} ангилал",
        'olympiad': olympiad,
        'school_summaries': school_summaries,
        'provinces': provinces,
        'schools': schools,
        'selected_pid': pid,
        'selected_sid': sid,
        'olympiad_id': olympiad_id,
    }

    return render(request, 'olympiad/results/province_summary.html', context)

