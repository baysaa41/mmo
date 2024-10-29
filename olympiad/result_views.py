from django.http import HttpResponse, JsonResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from olympiad.models import Olympiad, Result, SchoolYear, Award, Problem, OlympiadGroup
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
from olympiad.utils import adjusted_int_name
import csv
import os, io
import json
import re
from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django_tex.core import render_template_with_context
from django.db.models import Count

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

        olympiad.json_results = to_json(olympiad_id)
        olympiad.save()
    else:
        return HttpResponse("Olympiad doesn't exist.")
    return JsonResponse(olympiad.json_results, safe=False)

def to_json(olympiad_id):
    pd.options.display.float_format = '{:,.2f}'.format
    try:
        olympiad = Olympiad.objects.get(pk=olympiad_id)
    except Olympiad.DoesNotExist:
        return ''
    answers = Result.objects.filter(olympiad_id=olympiad_id)
    selected_fields = ['contestant__first_name', 'contestant_id', 'problem_id', 'score']
    json_str = list(answers.values(*selected_fields))
    return json_str


def json_view(request, olympiad_id):
    olympiad = Olympiad.objects.get(pk=olympiad_id)
    return render(request, 'olympiad/results/json_results.html', {'olympiad': olympiad})


def json_results(request, olympiad_id):
    try:
        olympiad = Olympiad.objects.get(pk=olympiad_id)
        data = olympiad.json_results
        valid_data = data.replace("'","\"")
        return JsonResponse(json.loads(valid_data), safe=False)
    except Olympiad.DoesNotExist:
        return JsonResponse({})

def pandasView(request, quiz_id):
    pd.options.display.float_format = '{:,.2f}'.format
    try:
        quiz = Olympiad.objects.get(pk=quiz_id)
    except ObjectDoesNotExist:
        return redirect('/')

    answers = Result.objects.filter(olympiad_id=quiz_id)
    users = User.objects.filter(is_active=True)
    answers_df = read_frame(answers, fieldnames=['contestant_id', 'problem_id', 'score'], verbose=False)
    users_df = read_frame(users, fieldnames=['last_name', 'first_name', 'id'], verbose=False)

    pivot = answers_df.pivot_table(index='contestant_id', columns='problem_id', values='score')
    pivot["Дүн"] = pivot.sum(axis=1)
    pivot.loc['AVG'] = pivot.mean()
    print(pivot)
    results = users_df.merge(pivot, left_on='id', right_on='contestant_id', how='right')
    results.sort_values(by='Дүн', ascending=False, inplace=True)
    # results["link"] = results["id"]
    results["link"] = results["id"].apply(
        lambda x: "<a href='/olympiads/result/{0}/{1}'>ХАРИУЛТ</a>".format(quiz_id, x))
    results.rename(columns={
        'id': 'ID',
        'first_name': 'Нэр',
        'last_name': 'Овог',
        'link': 'ХАРИУЛТ',
    }, inplace=True)
    results.index = np.arange(1, results.__len__() + 1)

    pd.set_option('colheader_justify', 'center')
    context = {
        'df': results.to_html(classes='table table-bordered table-hover', border=3, na_rep="", escape=False),
        'pivot': results.to_html(classes='table table-bordered table-hover', na_rep="", escape=False),
        'quiz': quiz,
    }
    return render(request, 'olympiad/pandas3.html', context)


def pandasView3(request, olympiad_id):
    provinces = Province.objects.all()
    pd.options.display.float_format = '{:,.1f}'.format
    try:
        olympiad = Olympiad.objects.get(pk=olympiad_id)
    except ObjectDoesNotExist:
        return redirect('/')

    pid = int(request.GET.get('p', 0))
    zid = int(request.GET.get('z', 0))
    answers = Result.objects.filter(olympiad_id=olympiad_id).order_by('problem__order')
    title = 'Нэгдсэн дүн'
    if pid > 0:
        if Province.objects.filter(pk=pid).exists():
            province = Province.objects.get(pk=pid)
            title = province.name
        answers = answers.filter(contestant__data__province_id=pid)
    elif zid > 0:
        if Zone.objects.filter(pk=zid).exists():
            zone = Zone.objects.filter(pk=zid).first()
            title = zone.name
        answers = answers.filter(contestant__data__province__zone_id=zid)

    if answers.count() == 0:
        context = {
            'df': '',
            'pivot': '',
            'quiz': '',
            'title': 'Оролцсон сурагч байхгүй.',
            'provinces': provinces,
        }
        return render(request, 'olympiad/pandas3.html', context)

    users = User.objects.filter(is_active=True)
    answers_df = read_frame(answers, fieldnames=['contestant_id', 'problem__order', 'score'], verbose=False)
    if olympiad.level_id == 1:
        users_df = read_frame(users, fieldnames=['id'], verbose=False)
    else:
        users_df = read_frame(users,
                              fieldnames=['last_name', 'first_name', 'id', 'data__province__name', 'data__school'],
                              verbose=False)

    answers_df['score'] = answers_df['score'].fillna(0)
    pivot = answers_df.pivot_table(index='contestant_id', columns='problem__order', values='score')
    pivot["Дүн"] = pivot.sum(axis=1)
    results = users_df.merge(pivot, left_on='id', right_on='contestant_id', how='right')
    awards = Award.objects.filter(olympiad_id=olympiad_id)
    awards_df = read_frame(awards, fieldnames=['place', 'contestant_id'], verbose=False).fillna(value='', inplace=True)
    results = results.merge(awards_df, left_on='id', right_on='contestant_id', how='left')
    results = results.drop(['contestant_id'], axis=1)
    results.sort_values(by='Дүн', ascending=False, inplace=True)
    results['id'].fillna(0).astype(int)
    results["link"] = results["id"].apply(lambda x: "<a href='/olympiads/result/{quiz_id}/{user_id:.0f}'> \
                                    <i class='fas fa-expand-wide'></i></a>".format(quiz_id=quiz_id, user_id=x))
    results['id'] = results['id'].apply(lambda x: "{id:.0f}".format(id=x))
    results.rename(columns={
        'id': 'ID',
        'first_name': 'Нэр',
        'last_name': 'Овог',
        'data__province__name': 'Аймаг/Дүүрэг',
        'data__school': 'Cургууль',
        'place': 'Медал',
        'link': '<i class="fas fa-expand-wide"></i>',
    }, inplace=True)
    results.index = np.arange(1, results.__len__() + 1)

    for item in quiz.problem_set.all().order_by('order'):
        results = results.rename(columns={item.order: '№' + str(item.order)})

    styled_df = (results.style.set_table_attributes('classes="table table-bordered table-hover"').set_table_styles([
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

    last_hack = styled_df.to_html(classes='table table-bordered table-hover', na_rep="", escape=False)
    last_hack = re.sub('<th class="blank level0" >&nbsp;</th>', '<th class="blank level0" >№</th>', last_hack)

    context = {
        'pivot': last_hack,
        'quiz': quiz,
        'title': title,
        'provinces': provinces,
    }
    return render(request, 'olympiad/pandas3.html', context)


def queryset_to_json(queryset):
    data = list(queryset.values())
    json_data = json.dumps(data, cls=DjangoJSONEncoder)
    return json_data


def getOlympiadResults(olympiad_id):
    answers = Result.objects.filter(olympiad_id=olympiad_id).order_by('problem__order')
    user_ids = answers.values_list('contestant', flat=True)
    users = User.objects.filter(id__in=user_ids)
    awards = Award.objects.filter(olympiad_id=olympiad_id)
    return users, answers, awards


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()  # Convert datetime to string format
        return super().default(obj)


def getJSONResults(request, olympiad_id):
    olympiad = Olympiad.objects.get(pk=olympiad_id)

    users, answers, awards = getOlympiadResults(olympiad_id)
    json_users = []
    for user in users:
        try:
            juser = {
                'id': user.id,
                'Овог': user.last_name,
                'Нэр': user.first_name,
                'Аймаг/Дүүрэг': user.data.province.name,
                'Сургууль': user.data.school,
                'Анги': user.data.grade.name
            }
            json_users.append(juser)
        except:
            pass

    json_answers = []
    for answer in answers:
        janswer = {
            'user_id': answer.contestant_id,
            'problem': answer.problem.order,
            'score': answer.score,
            'status': answer.state
        }
        json_answers.append(janswer)

    json_awards = []
    for award in awards:
        jaward = {
            'user_id': award.contestant_id,
            'award': award.place
        }
        json_awards.append(jaward)

    data = {
        'users': json_users,
        'answers': json_answers,
        'awards': json_awards
    }
    return JsonResponse(data)


def newResultView(request, olympiad_id):
    return render(request, "olympiad/javascript_pivot.html", {'olympiad': olympiad_id})


def pandasIMO64(request):
    ids = [117, 118, 120]
    quizzes = Olympiad.objects.filter(pk__in=ids).order_by('id')
    answers = Result.objects.filter(olympiad_id__in=ids)
    title = 'Нэгдсэн дүн'

    if answers.count() == 0:
        context = {
            'df': '',
            'pivot': '',
            'quiz': '',
            'title': 'Оролцсон сурагч байхгүй.',
        }
        return render(request, 'olympiad/pandas3.html', context)

    users = User.objects.filter(groups__name='IMO-64 сорилго')
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
    for quiz in quizzes:
        num = num + 1
        for item in quiz.problem_set.all().order_by('order'):
            # print(item.id, item.order)
            results = results.rename(columns={item.id: '№' + str(num) + '.' + str(item.order)})

    context = {
        'df': results.to_html(classes='table table-bordered table-hover', border=3, na_rep="", escape=False),
        'pivot': results.to_html(classes='table table-bordered table-hover', na_rep="", escape=False),
        'quiz': {
            'name': 'IMO-64 сорилго',
        },
        'title': title,
    }
    return render(request, 'olympiad/pandas3.html', context)


def olympiad_group_result_view(request,group_id):
    try:
        olympiad_group = OlympiadGroup.objects.get(pk=group_id)
    except OlympiadGroup.DoesNotExist:
        return render(request,'olympiad/results/no_olympiad.html')
    except Exception as e:
        return render(request, 'errors/error.html', {'message': str(e)})
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
        return render(request, 'olympiad/pandas3.html', context)

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
    return render(request, 'olympiad/pandas3.html', context)

def results_home(request):
    return HttpResponse("Zasvartai")
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
    return render(request, 'olympiad/results_home.html', context=context)

def olympiad_result_view(request, olympiad_id):
    return HttpResponse("Zasvartai")
    olympiad = Olympiad.objects.filter(id=olympiad_id).first()
    if olympiad.is_active() and not request.user.is_superuser:
        return HttpResponse("Test urgeljilj baina.")
    results = Result.objects.filter(olympiad=olympiad)
    with_province = True
    province = False

    s = request.GET.get('s', False)
    if s:
        if s == 'm':
            results = results.filter(contestant__data__gender='Эр')
        elif s == 'f':
            results = results.filter(contestant__data__gender='Эм')

    p = request.GET.get('p', False)
    if p:
        results = results.filter(contestant__data__province_id=p)
        province = Province.objects.filter(pk=p).first()
        with_province = False

    z = request.GET.get('z', False)
    if z:
        results = results.filter(contestant__data__province__zone_id=z)
        zone = Zone.objects.filter(pk=z).first()
        province = {'name': zone.name}
        with_province = False

    g = request.GET.get('g', False)
    if g:
        results = results.filter(contestant__data__grade_id=g)

    gle = request.GET.get('gle', False)
    if gle:
        results = results.filter(contestant__data__grade_id__lte=gle)

    head, sorted_values = format_results(olympiad, results, with_province)

    context = {'olympiad': olympiad, 'head': head, 'values': sorted_values, 'province': province}
    return render(request, 'olympiad/olympiad_result_view.html', context=context)


def olympiad_result_imo63_first(request):
    olympiad = {'name': 'IMO-63, I шат', 'id': 0}
    ids = [345, 346, 347, 348, 349, 350, 351, 352, 353, 354, 355, 356, 410, 411, 412, 413, 414, 415]
    results = Result.objects.filter(problem_id__in=ids)
    head, sorted_values = format_results(olympiad, results, False, ids)
    group = Group.objects.get(pk=10)
    for value in sorted_values:
        if int(value[len(value) - 2]) > 9:
            user_id = value[len(value) - 1]
            user = User.objects.get(pk=user_id)
            user.groups.add(group)
            user.save()

    context = {'olympiad': olympiad, 'head': head, 'values': sorted_values, 'province': False}
    return render(request, 'olympiad/olympiad_result_view.html', context=context)


def olympiad_result_imo63_third(request):
    olympiad = {'name': 'IMO-63, III шат', 'id': 0}
    ids = [392, 393, 394, 395, 396, 397, 398, 399, 400, 401, 402, 403, 410, 411, 412, 413, 414, 415]
    results = Result.objects.filter(problem_id__in=ids)
    head, sorted_values = format_results(olympiad, results, False, ids)
    group = Group.objects.get(pk=10)
    for value in sorted_values:
        if int(value[len(value) - 2]) > 9:
            user_id = value[len(value) - 1]
            user = User.objects.get(pk=user_id)
            user.groups.add(group)
            user.save()

    context = {'olympiad': olympiad, 'head': head, 'values': sorted_values, 'province': False}
    return render(request, 'olympiad/olympiad_result_view.html', context=context)


def olympiad_result_imo63_second(request):
    olympiad = {'name': 'IMO-63, II шат', 'id': 0}
    ids = [361, 362, 363, 364, 365, 366, 367, 368, 369]
    results = Result.objects.filter(problem_id__in=ids)
    head, sorted_values = format_results(olympiad, results, False, ids)

    context = {'olympiad': olympiad, 'head': head, 'values': sorted_values, 'province': False}
    return render(request, 'olympiad/olympiad_result_view.html', context=context)


def olympiad_result_imo62_third(request):
    olympiad = {'name': 'IMO-62, IMO сорил'}
    ids = [122, 123, 124, 126, 127, 128, 129, 130, 131, 132, 133, 134]
    results = Result.objects.filter(problem_id__in=ids)
    head, sorted_values = format_results(olympiad, results, False, ids)

    context = {'olympiad': olympiad, 'head': head, 'values': sorted_values, 'province': False}
    return render(request, 'olympiad/olympiad_result_view.html', context=context)

def get_contestant_ids(results):
    ids = []
    for result in results:
        ids.append(result.contestant.id)
    ids = list(dict.fromkeys(ids))
    return ids


def format_results(olympiad, results, with_province, ids=False):
    if ids:
        num = len(ids)
        problems_ids = ids
    else:
        num = len(olympiad.get_problem_ids())
        problems_ids = olympiad.get_problem_ids()
    if with_province:
        head = ('№', 'Овог, Нэр', 'ID', 'Аймаг, Дүүрэг')
    else:
        head = ('№', 'Овог, Нэр', 'ID', 'Сургууль')
    head = (*head, 'Анги')
    for i in range(1, num + 1):
        head = (*head, '№' + str(i))
    if ids:
        head = (*head, 'Дүн')
    else:
        head = (*head, 'Дүн', '<i class="far fa-expand"></i>')
    rows = []
    contestant_ids = get_contestant_ids(results)
    for contestant_id in contestant_ids:
        sum = 0.0
        contestant = User.objects.filter(id=contestant_id).first()
        contestant_results = results.filter(contestant_id=contestant_id)
        if with_province:
            try:
                row = str(contestant.last_name) + ', ' + str(
                    contestant.first_name), contestant.id, '<a href="?p={}">{}</a>'.format(
                    contestant.data.province.id, contestant.data.province.name)
            except:
                row = str(contestant.last_name) + ', ' + str(contestant.first_name), contestant.id, ''

        else:
            try:
                row = str(contestant.last_name) + ', ' + str(
                    contestant.first_name), contestant.id, contestant.data.province.name + ', ' + contestant.data.school
            except:
                row = str(contestant.id) + ', ' + str(
                    contestant.first_name), contestant.id, contestant.data.province.name
        try:
            grade = '<a href="?g={}">{}</a>'.format(contestant.data.grade.id, contestant.data.grade.name)
        except:
            grade = ''
        row = (*row, grade)

        for p_id in problems_ids:
            result = contestant_results.filter(problem_id=p_id).first()
            if result is not None:
                if result.score is not None:
                    score = result.score
                    sum = sum + result.score
                else:
                    score = '-'
                if result.state == 1:
                    score = '<span class="text-warning">' + str(score) + '</span>'
                elif result.state == 3:
                    score = '<span class="text-danger">' + str(score) + '</span>'
                row = (*row, score)
            else:
                row = (*row, 'x')

        row = (*row, sum, contestant_id)
        rows.append(row)

    sorted_values = sorted(rows, key=lambda t: -t[len(t) - 2])

    return head, sorted_values


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


def format_results_old(results):
    text = ''
    index = 1
    for item in results:
        text = text + '<tr><td>{}</td><td>{}</td>'.format(index, item['name'])
        text = text + '<td>{}</td><td>{}, {}</td>'.format(item['province'], item['school'], item['grade'])
        for i in item['results']:
            if i[1] == 0:
                text = text + "<td class='text-secondary'>{}</td>".format(i[0])
            elif i[1] == 1:
                text = text + "<td class='text-warning'>{}</td>".format(i[0])
            elif i[1] == 2:
                text = text + "<td class='text-info'>{}</td>".format(i[0])
            elif i[1] == 3:
                text = text + "<td class='text-danger'>{}</td>".format(i[0])
            else:
                text = text + "<td class='text-success'>{}</td>".format(i[0])
        text = text + '<th>{}</th><th>{}</th></tr>'.format(item['total'], item['medal'])
        index = index + 1

    return text


def sort_results(sub_li, cutoffs, medal_names=['Алтан медаль', 'Мөнгөн медаль', 'Хүрэл медаль']):
    l = len(sub_li)
    for i in range(0, l):
        for j in range(0, l - i - 1):
            if (sub_li[j]['total'] < sub_li[j + 1]['total']):
                tempo = sub_li[j]
                sub_li[j] = sub_li[j + 1]
                sub_li[j + 1] = tempo
    for i in range(0, l):
        if i < cutoffs[0]:
            sub_li[i]['medal'] = medal_names[0]
        elif i < cutoffs[1]:
            sub_li[i]['medal'] = medal_names[1]
        elif i < cutoffs[2]:
            sub_li[i]['medal'] = medal_names[2]
        else:
            sub_li[i]['medal'] = ''
    return sub_li


def create_results(olympiad_id):
    olympiad = Olympiad.objects.filter(pk=olympiad_id).first()
    contestants = olympiad.group.user_set.all()
    problems = olympiad.problem_set.all()
    for contestant in contestants:
        for problem in problems:
            create = Result.objects.get_or_create(olympiad=olympiad, problem=problem, contestant=contestant)
            if create[1]:
                result = create[0]
                result.grader_comment = 'Системд материалаа оруулаагүй. Системээс үүсгэсэн.'
                result.save()


# duureg
def import_results():
    file = '/home/deploy/khanuul.csv'
    # file = '/Users/baysa/Documents/igo-elem-results.csv'
    with open(file) as f:
        reader = csv.reader(f)
        i = 0
        for row in reader:
            i = i + 1
            try:
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=int(row[1]),
                                                               problem_id=int(row[2]))
                if result.score is None or result.score == 0:
                    result.score = int(row[3])
                    result.grader_comment = 'Дүнгийн хүснэгтээс хуулав.'
                    result.state = 2
                    result.save()
            except:
                print(row, i)
    return True


# dund1
def import_results_2():
    file = '/home/deploy/hotd1.csv'
    # file = '/Users/baysa/Documents/hotd1.csv'
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i = 0
        for row in reader:
            try:
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=68,
                                                               problem_id=370)
                result.score = int(row[1])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=68,
                                                               problem_id=371)
                result.score = int(row[2])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=68,
                                                               problem_id=372)
                result.score = int(row[3])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=68,
                                                               problem_id=373)
                result.score = int(row[4])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True


# ahlah
def import_results_3():
    file = '/home/deploy/hota2.csv'
    # file = '/Users/baysa/Documents/hota2.csv'
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i = 0
        for row in reader:
            try:
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=73,
                                                               problem_id=386)
                result.score = int(row[1])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=73,
                                                               problem_id=387)
                result.score = int(row[2])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=73,
                                                               problem_id=388)
                result.score = int(row[3])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True


# bagsh
def import_results_4():
    file = '/home/deploy/hotb2.csv'
    # file = '/Users/baysa/Documents/hotb2.csv'
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i = 0
        for row in reader:
            try:
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=74,
                                                               problem_id=389)
                result.score = int(row[1])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=74,
                                                               problem_id=390)
                result.score = int(row[2])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=74,
                                                               problem_id=391)
                result.score = int(row[3])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True


# dund2
def import_results_5():
    file = '/home/deploy/hotd21.csv'
    # file = '/Users/baysa/Documents/hotd21.csv'
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i = 0
        for row in reader:
            i = i + 1
            try:
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=69,
                                                               problem_id=374)
                result.score = int(row[1])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=69,
                                                               problem_id=375)
                result.score = int(row[2])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=69,
                                                               problem_id=376)
                result.score = int(row[3])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True


# dunduls
def import_uls_1():
    file = '/home/deploy/dunduls.csv'
    # file = '/Users/baysa/dunduls.csv'
    group = Group.objects.get(pk=15)
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i = 0
        for row in reader:
            print(row)
            try:
                user = User.objects.get(pk=int(row[0]))
                group.user_set.add(user)
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=75,
                                                               problem_id=404)
                result.score = int(row[1])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=75,
                                                               problem_id=405)
                result.score = int(row[2])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=75,
                                                               problem_id=406)
                result.score = int(row[3])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=75,
                                                               problem_id=407)
                result.score = int(row[4])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=75,
                                                               problem_id=408)
                result.score = int(row[5])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=75,
                                                               problem_id=409)
                result.score = int(row[6])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True


# ahlauls
def import_uls_2():
    file = '/home/deploy/ahlahuls.csv'
    # file = '/Users/baysa/ahlahuls.csv'
    group = Group.objects.get(pk=16)
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i = 0
        for row in reader:
            print(row)
            try:
                user = User.objects.get(pk=int(row[0]))
                group.user_set.add(user)
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=76,
                                                               problem_id=410)
                result.score = int(row[1])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=76,
                                                               problem_id=411)
                result.score = int(row[2])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=76,
                                                               problem_id=412)
                result.score = int(row[3])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=76,
                                                               problem_id=413)
                result.score = int(row[4])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=76,
                                                               problem_id=414)
                result.score = int(row[5])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=76,
                                                               problem_id=415)
                result.score = int(row[6])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True


# bagshuls
def import_uls_3():
    file = '/home/deploy/bagshuls.csv'
    # file = '/Users/baysa/bagshuls.csv'
    group = Group.objects.get(pk=17)
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i = 0
        for row in reader:
            print(row)
            try:
                user = User.objects.get(pk=int(row[0]))
                group.user_set.add(user)
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=77,
                                                               problem_id=416)
                result.score = int(row[1])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=77,
                                                               problem_id=417)
                result.score = int(row[2])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=77,
                                                               problem_id=418)
                result.score = int(row[3])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=77,
                                                               problem_id=419)
                result.score = int(row[4])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=77,
                                                               problem_id=420)
                result.score = int(row[5])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=77,
                                                               problem_id=421)
                result.score = int(row[6])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True


# bagshuls
def import_igo_elem():
    file = '/Users/baysa/Documents/igo-elem-results.csv'
    file = '/home/deploy/igo-elem-results.csv'
    group = Group.objects.get(pk=17)
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i = 0
        for row in reader:
            print(row)
            try:
                user = User.objects.get(pk=int(row[0]))
                group.user_set.add(user)
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=86,
                                                               problem_id=446)
                result.score = int(row[1])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=86,
                                                               problem_id=447)
                result.score = int(row[2])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=86,
                                                               problem_id=448)
                result.score = int(row[3])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=86,
                                                               problem_id=449)
                result.score = int(row[4])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=86,
                                                               problem_id=450)
                result.score = int(row[5])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True


# bagshuls
def import_igo_inter():
    file = '/Users/baysa/Documents/igo-inter-results.csv'
    file = '/home/deploy/igo-inter-results.csv'
    group = Group.objects.get(pk=17)
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i = 0
        for row in reader:
            print(row)
            try:
                user = User.objects.get(pk=int(row[0]))
                group.user_set.add(user)
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=87,
                                                               problem_id=451)
                result.score = int(row[1])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=87,
                                                               problem_id=452)
                result.score = int(row[2])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=87,
                                                               problem_id=453)
                result.score = int(row[3])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=87,
                                                               problem_id=454)
                result.score = int(row[4])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=87,
                                                               problem_id=455)
                result.score = int(row[5])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True


# bagshuls
def import_igo_advanced():
    file = '/Users/baysa/Documents/igo-advanced-results.csv'
    file = '/home/deploy/igo-advanced-results.csv'
    group = Group.objects.get(pk=17)
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i = 0
        for row in reader:
            print(row)
            try:
                user = User.objects.get(pk=int(row[0]))
                group.user_set.add(user)
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=88,
                                                               problem_id=456)
                result.score = int(row[1])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=88,
                                                               problem_id=457)
                result.score = int(row[2])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=88,
                                                               problem_id=458)
                result.score = int(row[3])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=88,
                                                               problem_id=459)
                result.score = int(row[4])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=88,
                                                               problem_id=460)
                result.score = int(row[5])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True


# bagshuls
def import_igo_bagsh():
    file = '/Users/baysa/Documents/igo-advanced-results.csv'
    file = '/home/deploy/igo-bagsh-results.csv'
    group = Group.objects.get(pk=17)
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i = 0
        for row in reader:
            print(row)
            try:
                user = User.objects.get(pk=int(row[0]))
                group.user_set.add(user)
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=89,
                                                               problem_id=463)
                result.score = int(row[1])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=89,
                                                               problem_id=464)
                result.score = int(row[2])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=89,
                                                               problem_id=465)
                result.score = int(row[3])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=89,
                                                               problem_id=466)
                result.score = int(row[4])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]), olympiad_id=89,
                                                               problem_id=467)
                result.score = int(row[5])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True


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


def importResultsOrg(df, oid, name):
    if Olympiad.objects.filter(pk=oid).exists():
        olympiad = Olympiad.objects.get(pk=oid)
    else:
        return HttpResponse("<h3>Олимпиад олдоогүй.</h3>")

    problems = olympiad.problem_set.all()
    size = problems.count()

    for item in df.iterrows():
        ind, row = item
        try:
            id = int(row['ID'])
            user = User.objects.get(pk=id)
        except:
            last_name = str(row[row.keys()[2]])
            first_name = str(row[row.keys()[3]])
            province_id = int(row[row.keys()[4]])
            school = str(row[row.keys()[5]])
            user = User.objects.filter(last_name=last_name,
                                       first_name=first_name,
                                       data__province_id=province_id).first()
            if user == None:
                username = 'user-' + str(row[row.keys()[4]]) + '-' + str(oid) + '-' + str(row[row.keys()[0]])
                user, created = User.objects.get_or_create(username=username)
                if created:
                    user.username = username
                    user.email = 'dm2020baysa@gmail.com'
                    user.last_name = str(row[row.keys()[2]]) + '-' + str(oid)
                    user.first_name = str(row[row.keys()[3]]) + '-' + str(oid)
                    user.save()
                    meta = UserMeta.objects.create(user=user)
                    meta.province_id = int(row[row.keys()[4]])
                    meta.school = str(row[row.keys()[5]])
                    meta.save()
                else:
                    print("{} user already exists".format(user.username))

            else:
                print(user.first_name)

        if user:
            print("importing {} user results".format(user.username))
            if user.first_name == '':
                user.last_name = str(row[row.keys()[2]]) + '-system'
                user.first_name = str(row[row.keys()[3]]) + '-system'
                user.save()

            i = 0
            for problem in problems:
                print(i)
                value = row[row.keys()[i + 7]]
                try:
                    answer, created = Result.objects.get_or_create(problem_id=problem.id,
                                                                   olympiad_id=oid,
                                                                   contestant_id=user.id)

                    try:
                        intval = int(value)
                        answer.answer = intval
                        answer.source_file = name
                        answer.save()
                    except Exception as e:
                        print(str(e))
                        pass

                except:
                    print("Алдаа:")
                    print(row[row.keys()[1]])
                    print(user.first_name)

                i = i + 1

    return len(df)


def secondRoundResults(request):
    if os.path.isdir('/Users/baysa/Downloads/2223'):
        dir = '/Users/baysa/Downloads/2223'
    else:
        dir = '/home/deploy/2023-II-2-dun'

    list = os.listdir(dir)
    print(list)
    num = 0
    for f in list:
        name = dir + '/' + f
        print(name)
        filename, file_extension = os.path.splitext(name)
        print(file_extension)
        if file_extension.lower() in ['.xls', '.xlsx']:
            try:
                print('C')
                df1 = pd.read_excel(name, 'C', engine='openpyxl')
                num = num + importResults(df1, 106, f)
            except:
                pass

            try:
                print('D')
                df2 = pd.read_excel(name, 'D', engine='openpyxl')
                num = num + importResults(df2, 107, f)
            except:
                pass

            try:
                print('E')
                df3 = pd.read_excel(name, 'E', engine='openpyxl')
                num = num + importResults(df3, 108, f)
            except:
                pass

            try:
                print('F')
                df4 = pd.read_excel(name, 'F', engine='openpyxl')
                num = num + importResults(df4, 109, f)
            except:
                pass

            try:
                print('S')
                df5 = pd.read_excel(name, 'S', engine='openpyxl')
                num = num + importResults(df5, 110, f)
            except:
                pass

            try:
                print('T')
                df6 = pd.read_excel(name, 'T', engine='openpyxl')
                num = num + importResults(df6, 111, f)
            except:
                pass

    return HttpResponse("<p>{} хариулт орууллаа.</p>".format(num))


def secondRoundResults2(request):
    if os.path.isdir('/Users/baysa/Downloads/2223'):
        dir = '/Users/baysa/Downloads/2223'
    else:
        dir = '/home/deploy/2023-II-2-dun'

    list = os.listdir(dir)
    print(list)
    num = 0
    for f in list:
        name = dir + '/' + f
        print(name)
        filename, file_extension = os.path.splitext(name)
        print(file_extension)
        if file_extension.lower() in ['.xls', '.xlsx']:

            try:
                print('D')
                df2 = pd.read_excel(name, 'D', engine='openpyxl')
                num = num + importResults(df2, 112, f)
            except:
                pass

            try:
                print('E')
                df3 = pd.read_excel(name, 'E', engine='openpyxl')
                num = num + importResults(df3, 113, f)
            except:
                pass

            try:
                print('F')
                df4 = pd.read_excel(name, 'F', engine='openpyxl')
                num = num + importResults(df4, 114, f)
            except:
                pass

            try:
                print('S')
                df5 = pd.read_excel(name, 'S', engine='openpyxl')
                num = num + importResults(df5, 115, f)
            except:
                pass

            try:
                print('T')
                df6 = pd.read_excel(name, 'T', engine='openpyxl')
                num = num + importResults(df6, 116, f)
            except:
                pass

    return HttpResponse("<p>{} хариулт орууллаа.</p>".format(num))


def secondRoundResults3():
    dir = '/home/deploy/results/2024-II-I-dun'

    list = os.listdir(dir)
    print(list)
    num = 0
    for f in list:
        name = dir + '/' + f
        print(name)
        filename, file_extension = os.path.splitext(name)
        print(file_extension)
        if file_extension.lower() in ['.xls', '.xlsx']:

            try:
                print('C')
                df2 = pd.read_excel(name, 'C (5-6)', engine='openpyxl')
                num = num + importResults(df2, 142, f)
            except Exception as e:
                print(e.__str__())
                pass
            try:
                print('D')
                df2 = pd.read_excel(name, 'D (7-8)', engine='openpyxl')
                num = num + importResults(df2, 143, f)
            except Exception as e:
                print(e.__str__())
                pass

            try:
                print('E')
                df3 = pd.read_excel(name, 'E (9-10)', engine='openpyxl')
                num = num + importResults(df3, 144, f)
            except Exception as e:
                print(e.__str__())
                pass

            try:
                print('F')
                df4 = pd.read_excel(name, 'F (11-12)', engine='openpyxl')
                num = num + importResults(df4, 145, f)
            except Exception as e:
                print(e.__str__())
                pass

            try:
                print('S')
                df5 = pd.read_excel(name, 'S (ББ)', engine='openpyxl')
                num = num + importResults(df5, 146, f)
            except Exception as e:
                print(e.__str__())
                pass

            try:
                print('T')
                df6 = pd.read_excel(name, 'T (ДБ)', engine='openpyxl')
                num = num + importResults(df6, 147, f)
            except Exception as e:
                print(e.__str__())
                pass

            os.rename(name, '/home/deploy/results/2024-II-I-dun/processed/' + f)

    return "<p>{} хариулт орууллаа.</p>".format(num)


def secondRoundResults4():
    dir = '/home/deploy/results/2024-II-II-dun'

    list = os.listdir(dir)
    print(list)
    num = 0
    for f in list:
        name = dir + '/' + f
        print(name)
        filename, file_extension = os.path.splitext(name)
        print(file_extension)
        if file_extension.lower() in ['.xls', '.xlsx']:

            try:
                print('D')
                df2 = pd.read_excel(name, 'D (7-8)', engine='openpyxl')
                num = num + importResults(df2, 149, f)
            except Exception as e:
                print(e.__str__())
                pass

            try:
                print('E')
                df3 = pd.read_excel(name, 'E (9-10)', engine='openpyxl')
                num = num + importResults(df3, 150, f)
            except Exception as e:
                print(e.__str__())
                pass

            try:
                print('F')
                df4 = pd.read_excel(name, 'F (11-12)', engine='openpyxl')
                num = num + importResults(df4, 151, f)
            except Exception as e:
                print(e.__str__())
                pass

            try:
                print('S')
                df5 = pd.read_excel(name, 'S (ББ)', engine='openpyxl')
                num = num + importResults(df5, 152, f)
            except Exception as e:
                print(e.__str__())
                pass

            try:
                print('T')
                df6 = pd.read_excel(name, 'T (ДБ)', engine='openpyxl')
                num = num + importResults(df6, 153, f)
            except Exception as e:
                print(e.__str__())
                pass

            os.rename(name, '/home/deploy/results/2024-II-II-dun/processed/' + f)

    return "<p>{} хариулт орууллаа.</p>".format(num)


def fixID():
    dir = '/home/deploy/results/fixes'

    list = os.listdir(dir)
    print(list)
    num = 0
    for f in list:
        name = dir + '/' + f
        print(name)
        filename, file_extension = os.path.splitext(name)
        print(file_extension)
        if file_extension.lower() in ['.xls', '.xlsx']:
            df = pd.read_excel(name, 'fixes', engine='openpyxl')
            for item in df.iterrows():
                ind, row = item
                results = Result.objects.filter(contestant_id=row['OLD'],olympiad_id=row['OLYMPIAD'])
                for result in results:
                    result.contestant_id = row['NEW']
                    result.save()
                awards = Award.objects.filter(contestant_id=row['OLD'],olympiad_id=row['OLYMPIAD'])
                for award in awards:
                    award.contestant_id = row['NEW']
                    award.save()

    return "<p>{} хариулт орууллаа.</p>".format(num)


def thirdRoundResults(request):
    dir = '/home/deploy/results/2023-III-dun'

    list = os.listdir(dir)
    print(list)
    num = 0
    for f in list:
        name = dir + '/' + f
        print(name)
        filename, file_extension = os.path.splitext(name)
        print(file_extension)
        if file_extension.lower() in ['.xls', '.xlsx']:

            try:
                print('E')
                df3 = pd.read_excel(name, 'E', engine='openpyxl')
                num = num + importResults(df3, 119, f)
            except:
                pass

            try:
                print('F')
                df4 = pd.read_excel(name, 'F', engine='openpyxl')
                num = num + importResults(df4, 120, f)
            except:
                pass

            try:
                print('T')
                df6 = pd.read_excel(name, 'T', engine='openpyxl')
                num = num + importResults(df6, 121, f)
            except:
                pass

    return HttpResponse("<p>{} хариулт орууллаа.</p>".format(num))


def igo10Results(request):
    dir = '/home/deploy/results/2023-igo'

    list = os.listdir(dir)
    print(list)
    num = 0
    for f in list:
        name = dir + '/' + f
        print(name)
        filename, file_extension = os.path.splitext(name)
        print(file_extension)
        if file_extension.lower() in ['.xls', '.xlsx']:

            try:
                print('D')
                df2 = pd.read_excel(name, 'D', engine='openpyxl')
                num = num + importResults(df2, 128, f)
            except:
                pass

            try:
                print('E')
                df3 = pd.read_excel(name, 'E', engine='openpyxl')
                num = num + importResults(df3, 129, f)
            except:
                pass

            try:
                print('F')
                df4 = pd.read_excel(name, 'F', engine='openpyxl')
                num = num + importResults(df4, 130, f)
            except:
                pass

            try:
                print('T')
                df6 = pd.read_excel(name, 'T', engine='openpyxl')
                num = num + importResults(df6, 131, f)
            except:
                pass

    return HttpResponse("<p>{} хариулт орууллаа.</p>".format(num))


def getResults(request):
    dir = '/home/deploy/results'

    list = os.listdir(dir)
    print(list)
    num = 0
    for f in list:
        name = dir + '/' + f
        # print(name)
        filename, file_extension = os.path.splitext(name)
        # print(file_extension)
        if file_extension.lower() in ['.xls', '.xlsx']:

            df = pd.read_excel(name, 'info', engine='openpyxl')

            for item0 in df.iterrows():
                idx, ol = item0
                print(ol['Ангилал'])
                print(ol['ID'])
                try:
                    dfr = pd.read_excel(name, ol['Ангилал'], engine='openpyxl')
                    oid = ol['ID']
                    olympiad = Olympiad.objects.get(pk=oid)
                    problems = olympiad.problem_set.all()
                    size = len(problems)

                    for item in dfr.iterrows():
                        ind, row = item
                        try:
                            user_id = int(row[row.keys()[1]])
                            user = User.objects.get(pk=user_id)
                        except:
                            last_name = str(row[row.keys()[2]])
                            first_name = str(row[row.keys()[3]])
                            province_id = int(row[row.keys()[4]])
                            school = str(row[row.keys()[5]])
                            user = User.objects.filter(last_name__startswith=last_name,
                                                       first_name__startswith=first_name,
                                                       data__province_id=province_id).first()
                            if not user:
                                username = 'user-' + str(row[row.keys()[4]]) + '-' + str(oid) + '-' + str(
                                    row[row.keys()[0]])
                                user, created = User.objects.get_or_create(username=username)
                                if created:
                                    print(username)
                                    user.username = username
                                    user.email = 'dm2020baysa@gmail.com'
                                    user.last_name = str(row[row.keys()[2]]) + '-' + str(oid)
                                    user.first_name = str(row[row.keys()[3]]) + '-' + str(oid)
                                    user.save()
                                    meta = UserMeta.objects.create(user=user)
                                    meta.province_id = int(row[row.keys()[4]])
                                    meta.school = str(row[row.keys()[5]])
                                    meta.save()

                        if user:
                            if user.first_name == '':
                                user.last_name = str(row[row.keys()[2]]) + '-system'
                                user.first_name = str(row[row.keys()[3]]) + '-system'
                                user.save()

                            i = 0
                            for problem in problems:
                                # print(i)
                                value = row[row.keys()[i + 7]]
                                try:
                                    answer, created = Result.objects.get_or_create(problem_id=problem.id,
                                                                                   olympiad_id=oid,
                                                                                   contestant_id=user.id)

                                    try:
                                        floatval = float(value)
                                        answer.score = floatval
                                        answer.source_file = name
                                        answer.save()
                                    except:
                                        pass

                                except:
                                    print("Алдаа:")
                                    print(row[row.keys()[1]])
                                    print(user.first_name)

                                i = i + 1
                except:
                    pass

    return HttpResponse("<p>{} хариулт орууллаа.</p>".format(num))


def importResults(df, oid, name):
    try:
        olympiad = Olympiad.objects.get(pk=oid)
    except:
        print('No Olympiad')
        return 0

    problems = olympiad.problem_set.all().order_by('order')

    size = len(problems)  # bodlogiin too

    for item in df.iterrows():
        ind, row = item
        print(row)
        try:
            id = int(row[row.keys()[1]])
            user = User.objects.get(pk=id)
        except:
            last_name = str(row[row.keys()[2]])
            first_name = str(row[row.keys()[3]])
            province_id = int(row[row.keys()[4]])
            school = str(row[row.keys()[5]])
            user = User.objects.filter(last_name__startswith=last_name,
                                       first_name__startswith=first_name,
                                       data__province_id=province_id).first()
            if not user:
                username = 'user-' + str(row[row.keys()[4]]) + '-' + str(oid) + '-' + str(row[row.keys()[0]])
                user, created = User.objects.get_or_create(username=username)
                if created:
                    user.username = username
                    user.email = 'mmo60official@gmail.com'
                    user.last_name = str(row[row.keys()[2]]) + '-' + str(oid)
                    user.first_name = str(row[row.keys()[3]]) + '-' + str(oid)
                    user.save()
                    meta = UserMeta.objects.create(user=user)
                    meta.province_id = int(row[row.keys()[4]])
                    meta.school = str(row[row.keys()[5]])
                    meta.save()

        if user:
            if user.first_name == '':
                user.last_name = str(row[row.keys()[2]]) + '-system'
                user.first_name = str(row[row.keys()[3]]) + '-system'
                user.save()

            i = 0
            for problem in problems:
                # print(i)
                value = row[row.keys()[i + 7]]
                try:
                    answer, created = Result.objects.get_or_create(problem_id=problem.id,
                                                                   olympiad_id=oid,
                                                                   contestant_id=user.id)

                    try:
                        floatval = float(value)
                        answer.score = np.floor(floatval)
                        answer.source_file = name
                        answer.save()
                    except:
                        pass

                except:
                    print("Алдаа:")
                    print(row[row.keys()[1]])
                    print(user.first_name)

                i = i + 1

    return len(df)


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


def result_view(request, olympiad_id):
    pid = int(request.GET.get('p', 0))
    zid = int(request.GET.get('z', 0))

    try:
        olympiad = Olympiad.objects.get(pk=olympiad_id)
    except:
        return render(request, 'olympiad/results/no_olympiad.html')
    results = Result.objects.filter(olympiad_id=olympiad_id).order_by('contestant_id', 'problem__order')

    if not results.exists():
        return render(request, 'olympiad/results/no_results.html')

    rows = list()
    for result in results:
        rows.append((result.contestant_id, result.problem_id, result.score))
    data = pd.DataFrame(rows)
    results_df = pd.pivot_table(data, index=[0], columns=[1], values=[2], aggfunc='sum')
    # results_df.fillna(0, inplace=True)

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
    results_df["Дүн"] = results_df.sum(axis=1)
    results_df[results_df.columns] = results_df[results_df.columns].applymap('{:.1f}'.format)
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
            elif zid == 12 and contestant.data.province.id > 21:
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

    if awards.exists():
        user_results_df = pd.merge(user_df, result_awards_df, left_on='ID', right_on='contestant_id', how='left')
        user_results_df['place'] = user_results_df['place'].fillna('')
        user_results_df.drop(['contestant_id'], axis=1, inplace=True)
        user_results_df.rename(columns={'place': 'Шагнал'},inplace=True)
    else:
        user_results_df = pd.merge(user_df, results_df, left_on='ID', right_index=True, how='left')

    user_results_df['Дүн'] = pd.to_numeric(user_results_df['Дүн'], errors='coerce')
    sorted_df = user_results_df.sort_values(by=['Дүн','ID'], ascending=[False,True])
    sorted_df[['Дүн']] = sorted_df[['Дүн']].applymap('{:.1f}'.format)
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
        return render(request, 'error.html', {'error': 'Бүлэг олдоогүй.'})
    except Olympiad.DoesNotExist:
       return render(request, 'error.html', {'error': 'Олимпиад олдоогүй.'})

    print(request.user.id,group.moderator.first().id)
    if not is_my_school_group(request.user.id,group_id): # and not request.user.is_staff:
        return render(request, 'error.html', {'error': 'Хандах эрхгүй.'})

    results = Result.objects.filter(olympiad_id=olympiad_id, contestant__groups=group).order_by('contestant_id', 'problem__order')

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

def problem_stats_view(request, problem_id):
    try:
        problem = Problem.objects.get(pk=problem_id)
    except:
        return render(request, 'errors/error.html', {'message': 'Бодлого олдоогүй.'})

    results = problem.get_results()
    for result in results:
        print(result.score)

    results_grouped = (Result.objects.filter(problem_id=problem_id,score__isnull=False)
                       .values('score').annotate(score_count=Count('score')).order_by('-score'))
    print(results_grouped)

    context = {
        'problem': problem,
        'count': results.count(),
        'results_grouped': results_grouped,
    }

    return render(request, 'olympiad/stats/problem_stats.html', context)