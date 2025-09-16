from django.http import HttpResponse, JsonResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404
from olympiad.models import Olympiad, Result, SchoolYear, Award, Problem, OlympiadGroup, ScoreSheet
from schools.models import School
from accounts.models import Province, Zone, UserMeta
from django.forms import modelformset_factory
from .forms import ResultsForm
import pandas as pd
import numpy as np
from django_pandas.io import read_frame
from django.db import connection
from django.contrib.auth.models import User, Group
from datetime import datetime, timezone
from olympiad.utils.data import adjusted_int_name
import csv
import os, io
import json
import re
from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django_tex.core import render_template_with_context
from django.db.models import Count
from django.views.decorators.cache import cache_page

ResultsFormSet = modelformset_factory(Result, form=ResultsForm, extra=0)

# nuhuh testiin hariug shinechileh
def update_results(request, olympiad_id):
    # create_results(olympiad_id)
    # return HttpResponse('Edit update')
    olympiad = Olympiad.objects.filter(pk=olympiad_id, type=1).first()
    if olympiad:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE olympiad_result SET score=0, state=5 WHERE olympiad_id=%s", [olympiad_id])
            cursor.execute("UPDATE olympiad_result r \
                            SET score = p.max_score \
                            FROM olympiad_problem p \
                            WHERE r.problem_id = p.id \
                                AND r.answer = p.numerical_answer \
                                AND p.olympiad_id = %s", [olympiad_id])

        # olympiad.json_results = to_json(olympiad_id)
        # olympiad.save()
    else:
        return HttpResponse("Olympiad doesn't exist.")
    # return JsonResponse(olympiad.json_results, safe=False)
    return HttpResponse("Ok.")

@cache_page(60 * 15)
def olympiad_group_result_view(request,group_id):
    try:
        olympiad_group = OlympiadGroup.objects.get(pk=group_id)
    except OlympiadGroup.DoesNotExist:
        return render(request,'olympiad/results/no_olympiad.html')
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
    results = results.reindex(columns1 + columns2 + columns3,axis=1)

    context = {
        'df': results.to_html(classes='table table-bordered table-hover', border=3, na_rep="", escape=False),
        'pivot': results.to_html(classes='table table-bordered table-hover', na_rep="", escape=False),
        'quiz': {
            'name': olympiad_group.name,
        },
        'title': title,
    }
    return render(request, 'olympiad/pandas_results_view.html', context)

def results_home(request):
    # return HttpResponse("Zasvartai")
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
    return render(request, 'olympiad/scoresheets_list.html', context=context)

def get_contestant_ids(results):
    ids = []
    for result in results:
        ids.append(result.contestant.id)
    ids = list(dict.fromkeys(ids))
    return ids


@login_required
def student_result_view(request, olympiad_id, contestant_id):
    results = Result.objects.filter(contestant_id=contestant_id, olympiad_id=olympiad_id).order_by('problem__order')
    contestant = User.objects.get(pk=contestant_id)
    olympiad = Olympiad.objects.get(pk=olympiad_id)
    if olympiad.is_active() and not request.user.is_superuser:
        return HttpResponse("Test urgeljilj baina.")
    username = contestant.last_name + ', ' + contestant.first_name
    return render(request, 'olympiad/student_result.html',
                  {'results': results, 'username': username, 'olympiad': olympiad})


def firstRoundResults(request):
    if os.path.isdir('/Users/baysa/Downloads/2223'):
        dir = '/Users/baysa/Downloads/2223'
    else:
        dir = '/home/deploy/2223'

    list = os.listdir(dir)
    print(list)
    num = 0
    for f in list:
        name = dir + '/' + f
        print(name)
        filename, file_extension = os.path.splitext(name)
        if file_extension.lower() in ['.xls', '.xlsx']:
            try:
                print('5-6')
                df1 = pd.read_excel(name, '5-6', engine='openpyxl')
                num = num + importResultsOrg(df1, 90, f)
            except:
                pass

            try:
                print('7-8')
                df2 = pd.read_excel(name, '7-8', engine='openpyxl')
                num = num + importResultsOrg(df2, 91, f)
            except:
                pass

            try:
                print('9-10')
                df3 = pd.read_excel(name, '9-10', engine='openpyxl')
                num = num + importResultsOrg(df3, 92, f)
            except:
                pass

            try:
                print('11-12')
                df4 = pd.read_excel(name, '11-12', engine='openpyxl')
                num = num + importResultsOrg(df4, 93, f)
            except:
                pass

    return HttpResponse("<p>{} хариулт орууллаа.</p>".format(num))


def createCertificate(request, quiz_id, contestant_id):
    if quiz_id == 102:
        template = '1.png'
    elif quiz_id == 100:
        template = '2.png'
    elif quiz_id == 101:
        template = '3.png'
    elif quiz_id == 103:
        template = '4.png'
    elif quiz_id == 104:
        template = '5.png'
    else:
        return HttpResponse("quiz_id do not match")
    try:
        contestant = User.objects.get(pk=contestant_id)
        results = Result.objects.filter(olympiad_id=quiz_id, contestant_id=contestant_id)
        total = 0
        for result in results:
            total = total + int(result.score)
            # if total == 0:
            # return HttpResponse("Оролцоогүй эсвэл оноо аваагүй.")
    except:
        return HttpResponse("contestant or results")

    TEX_ROOT = "/home/deploy/django/latex"
    xelatex = '/usr/bin/xelatex'
    os.chdir(TEX_ROOT)
    name = '{}-{}'.format(quiz_id, contestant_id)
    context = {
        'lastname': contestant.last_name,
        'firstname': contestant.first_name,
        'points': total,
        'template': template,
    }
    content = render_template_with_context('certificate.tex', context)
    with io.open('{}.tex'.format(name), "w") as f:
        print(content, file=f)
    os.system('{} -synctex=1 -interaction=nonstopmode {}.tex'.format(xelatex, name))
    os.system('{} {}.tex'.format(xelatex, name))

    return FileResponse(open('{}.pdf'.format(name), 'rb'))


@staff_member_required
def answers_view(request, olympiad_id):
    pid = int(request.GET.get('p', 0))
    zid = int(request.GET.get('z', 0))
    sid = int(request.GET.get('s', 0))

    try:
        olympiad = Olympiad.objects.get(pk=olympiad_id)
    except:
        return render(request, 'olympiad/results/no_olympiad.html')
    results = Result.objects.filter(olympiad_id=olympiad_id).order_by('contestant_id', 'problem__order')

    if not results.exists():
        return render(request, 'olympiad/results/no_results.html')

    rows = list()
    for result in results:
        rows.append((result.contestant_id, result.problem_id, result.answer))
    data = pd.DataFrame(rows)
    results_df = pd.pivot_table(data, index=[0], columns=[1], values=[2], aggfunc=np.sum, fill_value=0).astype(int)

    cols = list()
    for col in results_df.columns.values:
        try:
            problem = Problem.objects.get(pk=col[1])
            cols.append('№' + adjusted_int_name(problem.order))
        except:
            cols.append('not a problem!')
    results_df.columns = cols
    cols = sorted(cols)
    results_df = results_df[cols]
    results_df[results_df.columns] = results_df[results_df.columns].applymap('{:.0f}'.format)
    contestant_ids = list(results_df.index)
    contestants = User.objects.filter(pk__in=contestant_ids)
    awards = Award.objects.filter(olympiad_id=olympiad_id)
    if awards.exists():
        awards_df = read_frame(awards, fieldnames=['place', 'contestant_id'], verbose=False)
        result_awards_df = pd.merge(results_df, awards_df, left_index=True, right_on='contestant_id', how='left')

    users = list()
    for contestant in contestants:
        try:
            if pid and contestant.data.province_id == pid:
                users.append((contestant.id,
                              contestant.last_name,
                              contestant.first_name,
                              contestant.data.province.name,
                              contestant.data.school))
            elif zid and contestant.data.province.zone_id == zid:
                users.append((contestant.id,
                              contestant.last_name,
                              contestant.first_name,
                              contestant.data.province.name,
                              contestant.data.school))
            elif pid == 0 and zid == 0:
                users.append((contestant.id,
                              contestant.last_name,
                              contestant.first_name,
                              contestant.data.province.name,
                              contestant.data.school))
        except:
            print('datagui {}, {}'.format(contestant.id, contestant.first_name))
    if len(users) == 0:
        return render(request,'olympiad/results/no_results.html')
    user_df = pd.DataFrame(users)
    user_df.columns = ['ID', 'Овог', 'Нэр', 'Аймаг/Дүүрэг', 'Сургууль']

    user_results_df = pd.merge(user_df, results_df, left_on='ID', right_index=True, how='left')

    sorted_df = user_results_df.sort_values(by=['Аймаг/Дүүрэг', 'Сургууль', '№01', '№02', '№03'])
    sorted_df.index = np.arange(1, sorted_df.__len__() + 1)

    sorted_df["<i class='fas fa-expand-wide'></i>"] = sorted_df['ID'].apply(lambda x: "<a href='/olympiads/result/{}/{}'> \
                                        <i class='fas fa-expand-wide'></i></a>".format(str(olympiad_id), str(x)))


    pd.options.display.float_format = '{:.2f}'.format
    styled_df = (sorted_df.style.set_table_attributes('classes="table table-bordered table-hover"').set_table_styles([
        {
            'selector': 'th',
            'props': [('text-align', 'center')],
        },
        {
            'selector': 'td, th',
            'props': [('border', '1px solid #ccc')],
        },
        {
            'selector': 'td, th',
            'props': [('padding', '3px 5px 3px 5px')],
        },
    ]))

    # last hack
    content = styled_df.to_html()
    pattern = r'&nbsp;</th>'
    replacement = r'№</th>'
    content = re.sub(pattern, replacement, content)
    content = re.sub('>nan</td>', '>--</td>', content)

    name = "{}, {} ангилал, {} хичээлийн жил".format(olympiad.name, olympiad.level.name, olympiad.school_year.name)
    try:
        province = Province.objects.get(pk=pid)
        name = name + ', ' + province.name
    except:
        pass
    try:
        zone = Zone.objects.get(pk=zid)
        name = name + ', ' + zone.name
    except:
        pass

    context = {
        'title': olympiad.name,
        'name': name,
        'data': content
    }

    return render(request, 'olympiad/results/results.html', context)


def is_my_school_group(user_id, group_id):
    if School.objects.filter(user_id=user_id,group_id=group_id).exists():
        return True
    return False

def answers_view2(request, olympiad_id, group_id):
    try:
        group = Group.objects.get(pk=group_id)
        olympiad = Olympiad.objects.get(pk=olympiad_id)
    except Group.DoesNotExist:
        return render(request, 'messages/error.html', {'error': 'Бүлэг олдоогүй.'})
    except Olympiad.DoesNotExist:
       return render(request, 'messages/error.html', {'error': 'Олимпиад олдоогүй.'})

    if not is_my_school_group(request.user.id,group_id) and not request.user.is_staff:
        return render(request, 'messages/error.html', {'error': 'Хандах эрхгүй.'})

    results = Result.objects.filter(olympiad_id=olympiad_id, contestant__groups__id=group_id).order_by('contestant_id', 'problem__order')
    if not results.exists():
        return render(request, 'olympiad/results/no_results.html')

    rows = list()
    for result in results:
        rows.append((result.contestant_id, result.problem_id, result.answer))
    data = pd.DataFrame(rows)
    results_df = pd.pivot_table(data, index=[0], columns=[1], values=[2], aggfunc=np.sum, fill_value=0).astype(int)

    cols = list()
    for col in results_df.columns.values:
        try:
            problem = Problem.objects.get(pk=col[1])
            cols.append('№' + adjusted_int_name(problem.order))
        except:
            cols.append('not a problem!')
    results_df.columns = cols
    cols = sorted(cols)
    results_df = results_df[cols]
    results_df[results_df.columns] = results_df[results_df.columns].applymap('{:.0f}'.format)
    contestant_ids = list(results_df.index)
    contestants = group.user_set.all()
    awards = Award.objects.filter(olympiad_id=olympiad_id)
    if awards.exists():
        awards_df = read_frame(awards, fieldnames=['place', 'contestant_id'], verbose=False)
        result_awards_df = pd.merge(results_df, awards_df, left_index=True, right_on='contestant_id', how='left')

    users = list()
    for contestant in contestants:
        try:
            if contestant.data.level.id == olympiad.level.id:
                users.append((contestant.id,
                              contestant.last_name,
                              contestant.first_name,
                              contestant.data.province.name,
                              contestant.data.school))
        except Exception as e:
            pass #  return render(request, 'error.html', {'error': str(e)})

    if len(users) == 0:
        return render(request,'olympiad/results/no_results.html')
    user_df = pd.DataFrame(users)
    user_df.columns = ['ID', 'Овог', 'Нэр', 'Аймаг/Дүүрэг', 'Сургууль']

    user_results_df = pd.merge(user_df, results_df, left_on='ID', right_index=True, how='left')

    sorted_df = user_results_df.sort_values(by=['Аймаг/Дүүрэг', 'Сургууль', '№01', '№02', '№03'])
    sorted_df.index = np.arange(1, sorted_df.__len__() + 1)

    sorted_df["<i class='fas fa-expand-wide'></i>"] = sorted_df['ID'].apply(lambda x: "<a href='/olympiads/quiz/staff/{}/{}'> \
                                        <i class='fas fa-expand-wide'></i></a>".format(str(olympiad_id),str(x)))


    pd.options.display.float_format = '{:.2f}'.format
    styled_df = (sorted_df.style.set_table_attributes('classes="table table-bordered table-hover"').set_table_styles([
        {
            'selector': 'th',
            'props': [('text-align', 'center')],
        },
        {
            'selector': 'td, th',
            'props': [('border', '1px solid #ccc')],
        },
        {
            'selector': 'td, th',
            'props': [('padding', '3px 5px 3px 5px')],
        },
    ]))

    # last hack
    content = styled_df.to_html()
    pattern = r'&nbsp;</th>'
    replacement = r'№</th>'
    content = re.sub(pattern, replacement, content)
    content = re.sub('>nan</td>', '>--</td>', content)

    name = "{}, {} ангилал, {} хичээлийн жил".format(olympiad.name, olympiad.level.name, olympiad.school_year.name)

    context = {
        'title': olympiad.name,
        'name': name,
        'data': content
    }

    return render(request, 'olympiad/results/results.html', context)

from django.db.models import Avg, Max, Min

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
    }
    return render(request, 'olympiad/stats/problem_stats.html', context)



