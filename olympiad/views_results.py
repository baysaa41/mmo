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

    # Шинэ шүүлтүүрүүд
    official_filter = request.GET.get("official", "all")  # all, official, unofficial
    show_zero = request.GET.get("show_zero", "0") == "1"  # 0 оноог харуулах эсэх

    # --- 1. 'update=1' флагийг шалгах ---
    force_update = request.GET.get('clean', '0') == '1'

    # --- cache key үүсгэх ---
    cache_key = f"scores_{olympiad_id}_{province_id}_{zone_id}_{page_number}_{show_all}_{official_filter}_{show_zero}"

    cached_data = None

    # --- 2. 'force_update' ХИЙГЭЭГҮЙ үед л cache-с унших ---
    if not force_update:
        cached_data = cache.get(cache_key)

    # --- 3. Cache-д байхгүй ЭСВЭЛ 'force_update=1' үед ---
    if not cached_data:

        # Хэрэв force_update хийсэн бол мэдээлэх (заавал биш)
        if force_update:
            print(f"CACHE FORCED REFRESH: {cache_key}")

        # Queryset бэлтгэх
        scoresheets = ScoreSheet.objects.filter(olympiad=olympiad)

        # Problem тоог нэг удаа авах
        problem_count = olympiad.problem_set.count()
        problem_range = problem_count + 1

        # --- 0 оноог шүүх (default: харуулахгүй) ---
        if not show_zero:
            scoresheets = scoresheets.exclude(total=0)

        # --- Албан ёсны шүүлтүүр ---
        if official_filter == "official":
            scoresheets = scoresheets.filter(is_official=True)
        elif official_filter == "unofficial":
            scoresheets = scoresheets.filter(is_official=False)

        # --- Аймаг/Бүс шүүлтүүр ---
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

        scoresheets = scoresheets.select_related(
            "user__data__school__province",
            "user__data__province",
            "school__province"
        ).order_by("-is_official", list_rank_field, "-total")

        # --- Database түвшинд pagination хийх ---
        paginator = Paginator(scoresheets, 50)
        page_obj = paginator.get_page(page_number)

        # --- Зөвхөн тухайн хуудасны өгөгдлийг dict болгох ---
        score_data_list = []
        for sheet in page_obj:
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
                    "is_official": sheet.is_official,
                })
            except Exception as e:
                print("Алдаа:", e, sheet, sheet.user.id)

        # Cache-д хадгалах өгөгдөл (template-д page_obj шиг ашиглахын тулд)
        cached_data = {
            'score_data_list': score_data_list,
            'number': page_obj.number,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'previous_page_number': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None,
            'problem_range': problem_range,
            'paginator': {
                'num_pages': paginator.num_pages,
                'page_range': list(paginator.page_range),
            }
        }

        # --- 4. Cache-д шинээр дарж бичих ---
        cache.set(cache_key, cached_data, 3600)

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
        "score_data": cached_data['score_data_list'],
        "page_obj": cached_data,
        "user_score_data": user_score_data,
        "problem_range": range(1, cached_data['problem_range']),
        "selected_province": province_id,
        "selected_zone": zone_id,
        "official_filter": official_filter,
        "show_zero": show_zero,
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

@login_required
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
            # Хариулт болон оноог хамт авах
            rows = list(results.values_list('contestant_id', 'problem_id', 'answer', 'score'))
            data = pd.DataFrame(rows, columns=['contestant_id', 'problem_id', 'answer', 'score'])

            # Хариултын хүснэгт
            results_df = pd.pivot_table(data, index='contestant_id', columns='problem_id', values='answer', aggfunc='sum')

            # Онооны хүснэгт (нийлбэр тооцоход)
            score_df = pd.pivot_table(data, index='contestant_id', columns='problem_id', values='score', aggfunc='sum', fill_value=0)

            problem_ids = results_df.columns.values
            problem_orders = {p.id: f'№{p.order:02d}' for p in Problem.objects.filter(id__in=problem_ids)}

            # Баганын нэрийг солих (results_df болон score_df хоёуланд)
            col_mapping = {col: problem_orders.get(col, 'Unknown') for col in results_df.columns}
            results_df.columns = [col_mapping[col] for col in results_df.columns]
            score_df.columns = [col_mapping.get(col, col) for col in score_df.columns]

            results_df = results_df[sorted(results_df.columns)]
            score_df = score_df[[col for col in sorted(results_df.columns) if col in score_df.columns]]

            # Нийт оноо нэмэх
            results_df['Нийт'] = score_df.sum(axis=1)

            contestant_ids = list(results_df.index)
            contestants_data = User.objects.filter(pk__in=contestant_ids).values('id', 'last_name', 'first_name')
            user_df = pd.DataFrame(list(contestants_data))
            user_df.columns = ['ID', 'Овог', 'Нэр']

            user_results_df = pd.merge(user_df, results_df, left_on='ID', right_index=True, how='left')

            # Оноог мөн merge хийх (өнгө тодорхойлоход хэрэглэнэ)
            score_df_merged = pd.merge(user_df[['ID']], score_df, left_on='ID', right_index=True, how='left')

            # Нийт оноогоор буурахаар эрэмбэлэх
            sorted_df = user_results_df.sort_values(
                by=['Нийт', 'Овог', 'Нэр'],
                ascending=[False, True, True]
            )
            score_df_merged = score_df_merged.loc[sorted_df.index]

            sorted_df = sorted_df.drop(columns=['ID'])
            score_df_merged = score_df_merged.drop(columns=['ID'])

            sorted_df.index = np.arange(1, len(sorted_df) + 1)
            score_df_merged.index = sorted_df.index

            # Тоон багануудын жагсаалт
            numeric_columns = [col for col in sorted_df.columns if str(col).startswith('№')]

            # Форматчилах функц
            formatter = lambda val: '{:.0f}'.format(val) if val > 0 else '---'

            # Зөв хариултыг ногоон суурь өнгөөр тодруулах
            def highlight_correct(val, score_val):
                if pd.isna(score_val) or score_val == 0:
                    return ''
                return 'background-color: #d4edda'  # Ногоон

            def apply_highlights(row):
                styles = [''] * len(row)
                for i, col in enumerate(row.index):
                    if col in numeric_columns and col in score_df_merged.columns:
                        score_val = score_df_merged.loc[row.name, col]
                        if not pd.isna(score_val) and score_val > 0:
                            styles[i] = 'background-color: #d4edda'
                return styles

            # HTML руу хөрвүүлэх
            styled_df = (sorted_df.style
                                  .apply(apply_highlights, axis=1)
                                  .format(formatter, subset=numeric_columns, na_rep="-")
                                  .format('{:.1f}'.format, subset=['Нийт'])
                                  .set_table_attributes('class="table table-bordered table-hover"'))
            context_data = styled_df.to_html()

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

    # --- Шинэ хувьсагчдыг энд тунхаглах ---
    province = None
    total_school_count = None
    participating_school_count = None
    non_participating_schools = None
    total_student_count = None
    participating_student_count = None


    if pid > 0:
        # --- АЙМАГ СОНГОГДСОН ҮЕД (Хуучин логик хэвээрээ) ---
        try:
            province = Province.objects.get(pk=pid)
        except Province.DoesNotExist:
            pass

        schools_in_province = (School.objects
                               .filter(province_id=pid)
                               .select_related('user', 'user__data')
                               .order_by('name'))

        for school in schools_in_province:
            results = Result.objects.filter(olympiad_id=olympiad_id, contestant__data__school_id=school.id)
            contestant_ids = results.values_list('contestant_id', flat=True).distinct()
            total_count = contestant_ids.count()
            empty_row_count = 0
            sample_data_html = ""
            if total_count > 0:
                positive_scorers_count = results.filter(score__gt=0).values_list('contestant_id', flat=True).distinct().count()
                empty_row_count = total_count - positive_scorers_count
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
                sample_data_html = "<p class='text-muted fst-italic'>Энэ олимпиадад оролцсон сурагч олдсонгүй.</p>"
            school_summaries.append({
                'school': school,
                'total_count': total_count,
                'empty_row_count': empty_row_count,
                'sample_data_html': sample_data_html,
            })

    else:
        # --- АЙМАГ СОНГОГДООГҮЙ ҮЕД (pid == 0) ---

        # 1. Сургуулийн тоон мэдээлэл
        participating_school_ids = (Result.objects
                                      .filter(olympiad_id=olympiad_id, contestant__data__school__isnull=False)
                                      .values_list('contestant__data__school_id', flat=True)
                                      .distinct())
        participating_school_count = participating_school_ids.count()
        total_school_count = School.objects.count()

        # 2. Оролцоогүй сургуулиудын жагсаалт
        non_participating_schools = (School.objects
                                     .exclude(id__in=participating_school_ids)
                                     .select_related('province', 'user', 'user__data')
                                     .order_by('province__id', 'name'))

        # 3. Сурагчдын тоон мэдээлэл (ШИНЭЧЛЭГДСЭН ХЭСЭГ)

        # "Нийт (энэ ангиллын) сурагч"
        # Хэрэглэгчийн хүсэлтээр нийт сурагчдыг олимпиадын
        # ангилалтай (level) таарч буй нийт хэрэглэгчээр тооцоолно.
        # Энэ нь user.data.level гэж талбар байхыг шаардана.
        try:
            if olympiad.level:
                # User.data.level нь olympiad.level-тэй ижил сурагчдыг тоолно
                total_student_count = User.objects.filter(data__level=olympiad.level).count()
            else:
                # Олимпиадад level тохируулаагүй бол 0 гэж үзэх
                total_student_count = 0
        except Exception as e:
            # `data__level` гэж талбар байхгүй эсвэл алдаа гарвал
            print(f"Total student count error (falling back to ScoreSheet): {e}")
            # ХУУЧИН АРГА: Зөвхөн ScoreSheet үүссэн сурагчдыг тоолно
            total_student_count = ScoreSheet.objects.filter(olympiad_id=olympiad_id).count()


        # "Хариулт ирүүлсэн" (Энэ хэвээрээ)
        participating_student_count = Result.objects.filter(olympiad_id=olympiad_id).values('contestant_id').distinct().count()


    # --- Контекстыг шинэчлэх ---
    context = {
        'title': f"{province.name if province else 'Аймгийн'} тойм" if pid > 0 else "Улсын хэмжээний тойм",
        'name': f"{olympiad.name}, {olympiad.level.name if olympiad.level else 'Ангилалгүй'} ангилал",
        'olympiad': olympiad,
        'school_summaries': school_summaries,
        'provinces': provinces,
        'schools': schools,
        'selected_pid': pid,
        'selected_sid': sid,
        'olympiad_id': olympiad_id,

        'total_school_count': total_school_count,
        'participating_school_count': participating_school_count,
        'non_participating_schools': non_participating_schools,
        'total_student_count': total_student_count,
        'participating_student_count': participating_student_count,
    }

    return render(request, 'olympiad/results/province_summary.html', context)


@login_required
def first_round_stats(request):
    """
    1-р даваа (Сургуулийн олимпиад)-д аймаг, дүүрэг бүрээс
    хэдэн сургууль, хэдэн сурагч оролцсоныг харуулах
    """
    # Хичээлийн жилийг сонгох
    now = datetime.now(timezone.utc)
    school_year = SchoolYear.objects.filter(start__lt=now, end__gt=now).first()
    year_id = request.GET.get('year', school_year.id if school_year else None)
    year = SchoolYear.objects.filter(pk=year_id).first() if year_id else None

    # Олимпиад сонгох (заавал биш, сонгоогүй бол хамгийг багтаана)
    olympiad_id = request.GET.get('olympiad', None)

    prev = SchoolYear.objects.filter(pk=year.id - 1).first() if year else None
    next = SchoolYear.objects.filter(pk=year.id + 1).first() if year else None

    # 1-р даваа (round=1) олимпиадуудыг авах
    olympiads = Olympiad.objects.filter(round=1, is_open=True)
    if year:
        olympiads = olympiads.filter(school_year=year)

    olympiads = olympiads.order_by('name', 'level')

    # Тухайн олимпиад(ууд)-аас үр дүн авах
    if olympiad_id:
        # Нэг олимпиадыг сонгосон бол
        results_query = Result.objects.filter(olympiad_id=olympiad_id)
        selected_olympiad = Olympiad.objects.filter(pk=olympiad_id).first()
    else:
        # Сонгоогүй бол бүх 1-р даваа олимпиадыг багтаана
        results_query = Result.objects.filter(olympiad__in=olympiads)
        selected_olympiad = None

    # Бүх аймгийг авах
    provinces = Province.objects.all().order_by('name')

    # Аймаг бүрээр статистик бэлтгэх
    province_stats = []

    for province in provinces:
        # Энэ аймгаас оролцсон Results-үүд
        province_results = results_query.filter(
            contestant__data__province=province
        )

        # Сургуулийн тоо (давхардсан тоолохгүйгээр)
        school_count = province_results.filter(
            contestant__data__school__isnull=False
        ).values('contestant__data__school').distinct().count()

        # Сурагчдын тоо (давхардсан тоолохгүйгээр)
        student_count = province_results.values('contestant').distinct().count()

        # Хэрэв оролцсон бол жагсаалтанд нэмэх
        if school_count > 0 or student_count > 0:
            province_stats.append({
                'province': province,
                'school_count': school_count,
                'student_count': student_count,
            })

    # Нийт тоо
    total_schools = sum(s['school_count'] for s in province_stats)
    total_students = sum(s['student_count'] for s in province_stats)

    context = {
        'title': '1-р даваа - Аймаг, дүүргээр',
        'province_stats': province_stats,
        'total_schools': total_schools,
        'total_students': total_students,
        'olympiads': olympiads,
        'selected_olympiad': selected_olympiad,
        'year': year,
        'prev': prev,
        'next': next,
    }

    return render(request, 'olympiad/results/first_round_stats.html', context)


@staff_member_required
def cheating_analysis_view(request, olympiad_id):
    """
    Сургуулиудын хуулалтын шинжилгээний хуудас
    """
    from .cheating_analysis import analyze_olympiad_cheating
    from collections import defaultdict

    try:
        olympiad = Olympiad.objects.get(pk=olympiad_id)
    except Olympiad.DoesNotExist:
        return render(request, 'olympiad/results/no_olympiad.html')

    # Run analysis
    results_df = analyze_olympiad_cheating(olympiad_id)

    # Convert to list of dicts for template
    if not results_df.empty:
        results_data = results_df.to_dict('records')
    else:
        results_data = []

    # Group by province
    provinces_dict = defaultdict(list)
    for item in results_data:
        province_name = item.get('province_name', 'Тодорхойгүй')
        provinces_dict[province_name].append(item)

    # Sort provinces and schools within each province
    provinces_data = []
    for province_name in sorted(provinces_dict.keys()):
        schools = sorted(provinces_dict[province_name], key=lambda x: -x['CPS'])
        provinces_data.append({
            'name': province_name,
            'schools': schools,
            'school_count': len(schools)
        })

    context = {
        'olympiad': olympiad,
        'provinces': provinces_data,
        'total_schools': len(results_data),
    }

    return render(request, 'olympiad/results/cheating_analysis.html', context)