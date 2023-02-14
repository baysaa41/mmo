from django.http import HttpResponse, JsonResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from olympiad.models import Olympiad, Result, SchoolYear
from accounts.models import Province, Zone, UserMeta
from django.forms import modelformset_factory
from .forms import ResultsForm
import pandas as pd
import numpy as np
from django_pandas.io import read_frame
from django.db import connection
from django.contrib.auth.models import User, Group
from datetime import datetime, timezone
import csv
import os, io
from django_tex.core import render_template_with_context

ResultsFormSet = modelformset_factory(Result, form=ResultsForm, extra=0)


def update_results(request, olympiad_id):
    # create_results(olympiad_id)
    # return HttpResponse('Edit update')
    olympiad = Olympiad.objects.filter(pk=olympiad_id, type=1).first()
    if olympiad:
        with connection.cursor() as cursor:
            cursor.execute("update olympiad_result set score=0, state=5 where olympiad_id=%s", [olympiad_id])
            cursor.execute("update olympiad_result r join olympiad_problem p on r.problem_id=p.id and \
                r.answer=p.numerical_answer set r.score=p.max_score where p.olympiad_id=%s", [olympiad_id])
    else:
        return HttpResponse("Olympiad doesn't exist.")
    return HttpResponse('Results are updated.')


def pandasView(request,quiz_id):
    pd.options.display.float_format = '{:,.2f}'.format
    try:
        quiz = Olympiad.objects.get(pk=quiz_id)
    except ObjectDoesNotExist:
        return redirect('/')

    answers = Result.objects.filter(olympiad_id=quiz_id)
    users = User.objects.filter(is_active=True)
    answers_df = read_frame(answers,fieldnames=['contestant_id','problem_id','score'],verbose=False)
    users_df = read_frame(users,fieldnames=['last_name','first_name','id'],verbose=False)

    pivot = answers_df.pivot_table(index='contestant_id',columns='problem_id',values='score')
    pivot["Дүн"]=pivot.sum(axis=1)
    pivot.loc['AVG'] = pivot.mean()
    print(pivot)
    results = users_df.merge(pivot,left_on='id',right_on='contestant_id',how='right')
    results.sort_values(by='Дүн',ascending=False,inplace=True)
    results["link"] = results["id"]
    results["link"] = results["link"].apply(lambda x: "<a href='/olympiads/result/{0}/{1}'>ХАРИУЛТ</a>".format(quiz_id,x))
    results.rename(columns={
        'id': 'ID',
        'first_name': 'Нэр',
        'last_name': 'Овог',
        'link': 'ХАРИУЛТ',
    },inplace=True)
    results.index = np.arange(1,results.__len__()+1)


    pd.set_option('colheader_justify', 'center')
    context = {
        'df': results.to_html(classes='table table-bordered table-hover',border=3,na_rep="",escape=False),
        'pivot':  results.to_html(classes='table table-bordered table-hover',na_rep="",escape=False),
        'quiz': quiz,
    }
    return render(request, 'myquiz/pandas.html', context)


def pandasView3(request,olympiad_id):
    quiz_id=olympiad_id
    pd.options.display.float_format = '{:,.0f}'.format
    try:
        quiz = Olympiad.objects.get(pk=quiz_id)
    except ObjectDoesNotExist:
        return redirect('/')

    pid = int(request.GET.get('p',0))
    zid = int(request.GET.get('z',0))
    answers = Result.objects.filter(olympiad_id=quiz_id)
    title = 'Нэгдсэн дүн'
    if pid>0:
        province = Province.objects.filter(pk=pid).first()
        if province:
            title = province.name
        answers = answers.filter(contestant__data__province_id=pid)
    elif zid>0:
        zone = Zone.objects.filter(pk=zid).first()
        if zone:
            title = zone.name
        answers = answers.filter(contestant__data__province__zone_id=zid)

    if answers.count() == 0:
        context = {
            'df': '',
            'pivot': '',
            'quiz': '',
            'title': 'Оролцсон сурагч байхгүй.'
        }
        return render(request, 'myquiz/pandas.html', context)

    users = User.objects.filter(is_active=True)
    answers_df = read_frame(answers,fieldnames=['contestant_id','problem_id','score'],verbose=False)
    if quiz.level_id == 1:
        users_df = read_frame(users, fieldnames=['id'], verbose=False)
    else:
        users_df = read_frame(users,fieldnames=['last_name','first_name','id','data__school'],verbose=False)


    answers_df['score'] = answers_df['score'].fillna(0)
    pivot = answers_df.pivot_table(index='contestant_id',columns='problem_id',values='score')
    pivot["Дүн"] = pivot.sum(axis=1)
    results = users_df.merge(pivot,left_on='id',right_on='contestant_id',how='right')
    results.sort_values(by='Дүн',ascending=False,inplace=True)
    results['id'].fillna(0).astype(int)
    results["link"] = results["id"].apply(lambda x: "<a href='/olympiads/result/{quiz_id}/{user_id:.0f}'><i class='fas fa-expand-wide'></i></a>".format(quiz_id=quiz_id,user_id=x))
    results.rename(columns={
        'id': 'ID',
        'first_name': 'Нэр',
        'last_name': 'Овог',
        'data__school': 'Cургууль',
        'link': '<i class="fas fa-expand-wide"></i>',
    },inplace=True)
    results.index = np.arange(1,results.__len__()+1)


    pd.set_option('colheader_justify', 'center')

    for item in quiz.problem_set.all().order_by('order'):
        # print(item.id, item.order)
        results = results.rename(columns={item.id: '№' + str(item.order)})

    context = {
        'df': results.to_html(classes='table table-bordered table-hover',border=3,na_rep="",escape=False),
        'pivot':  results.to_html(classes='table table-bordered table-hover',na_rep="",escape=False),
        'quiz': quiz,
        'title': title
    }
    return render(request, 'myquiz/pandas.html', context)

def fix_results(request):
    return False


def pandasView2(request, quiz_id):
    pd.options.display.float_format = '{:,.2f}'.format

    with connection.cursor() as cursor:
        cursor.execute('''select u.username, p.`order`, r.score, r.answer from olympiad_result r join auth_user u \
                        on r.`contestant_id`=u.id join olympiad_problem p on r.`problem_id`=p.id \
                        where r.olympiad_id=%s''',
                       [quiz_id])
        results = cursor.fetchall()
    data = pd.DataFrame(results)
    if data.empty:
        pivot = 'Өгөгдөл олдсонгүй!'
        describe = pivot
    else:
        pivot = data.pivot_table(index=[0], columns=[1], values=[2], fill_value=0)
        pivot = pivot.reindex(sorted(pivot.columns), axis=1)
        pivot['Дүн'] = pivot.sum(axis=1)
        pivot = pivot.sort_values(by='Дүн', ascending=False)
        pivot.loc['Дундаж'] = pivot.mean()
        corr = pivot.corr()
        dun = 100 * corr.iloc[[-1]]
        dun = dun.rename(index={'Дүн': 'ЯЧИ'})
        pivot = pivot.append(dun)
        pivot = pivot.to_html(index_names=False)
        describe = data.describe().to_html()

    context = {
        'df': data.to_html(index=False),
        'describe': describe,
        'pivot': pivot
    }
    return render(request, 'olympiad/pandas.html', context)


def results_home(request):
    now = datetime.now(timezone.utc)
    mode = request.GET.get('mode', 0)
    school_year = SchoolYear.objects.filter(start__lt=now, end__gt=now).first()
    id = request.GET.get('year', school_year.id)
    year = SchoolYear.objects.filter(pk=id).first()
    prev = SchoolYear.objects.filter(pk=year.id - 1).first()
    next = SchoolYear.objects.filter(pk=year.id + 1).first()

    olympiads = Olympiad.objects.filter(is_open=True).order_by('-school_year_id','name','level')

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


def olympiad_result_egmo(request):
    olympiad = {'name': 'EGMO', 'id': 0}
    ids = [299,300,301,302,303,304,305,306,307,308,309,310]
    results = Result.objects.filter(problem_id__in=ids)
    head, sorted_values = format_results(olympiad, results, False, ids)
    context = {'olympiad': olympiad, 'head': head, 'values': sorted_values, 'province': False}
    return render(request, 'olympiad/olympiad_result_view.html', context=context)

def olympiad_result_imo63_first(request):
    olympiad = {'name': 'IMO-63, I шат', 'id': 0}
    ids = [345,346,347,348,349,350,351,352,353,354,355,356,410,411,412,413,414,415]
    results = Result.objects.filter(problem_id__in=ids)
    head, sorted_values = format_results(olympiad, results, False, ids)
    group = Group.objects.get(pk=10)
    for value in sorted_values:
        if int(value[len(value) - 2]) > 9:
            user_id = value[len(value)-1]
            user = User.objects.get(pk=user_id)
            user.groups.add(group)
            user.save()

    context = {'olympiad': olympiad, 'head': head, 'values': sorted_values, 'province': False}
    return render(request, 'olympiad/olympiad_result_view.html', context=context)

def olympiad_result_imo63_third(request):
    olympiad = {'name': 'IMO-63, III шат', 'id': 0}
    ids = [392,393,394,395,396,397,398,399,400,401,402,403,410,411,412,413,414,415]
    results = Result.objects.filter(problem_id__in=ids)
    head, sorted_values = format_results(olympiad, results, False, ids)
    group = Group.objects.get(pk=10)
    for value in sorted_values:
        if int(value[len(value) - 2]) > 9:
            user_id = value[len(value)-1]
            user = User.objects.get(pk=user_id)
            user.groups.add(group)
            user.save()

    context = {'olympiad': olympiad, 'head': head, 'values': sorted_values, 'province': False}
    return render(request, 'olympiad/olympiad_result_view.html', context=context)


def olympiad_result_imo63_second(request):
    olympiad = {'name': 'IMO-63, II шат', 'id': 0}
    ids = [361,362,363,364,365,366,367,368,369]
    results = Result.objects.filter(problem_id__in=ids)
    head, sorted_values = format_results(olympiad, results, False, ids)

    context = {'olympiad': olympiad, 'head': head, 'values': sorted_values, 'province': False}
    return render(request, 'olympiad/olympiad_result_view.html', context=context)


def olympiad_result_imo62_third(request):
    olympiad = {'name': 'IMO-62, IMO сорил'}
    ids = [122,123,124,126,127,128,129,130,131,132,133,134]
    results = Result.objects.filter(problem_id__in=ids)
    head, sorted_values = format_results(olympiad, results, False, ids)

    context = {'olympiad': olympiad, 'head': head, 'values': sorted_values, 'province': False}
    return render(request, 'olympiad/olympiad_result_view.html', context=context)


def olympiad_result_mmo58_second_dund2(request):
    olympiad = {'name': 'ММО-58, Хот, Дунд 2 ангилал'}
    ids = [374,375,376,383,384,385]
    results = Result.objects.filter(problem_id__in=ids)
    head, sorted_values = format_results(olympiad, results, False, ids)

    context = {'olympiad': olympiad, 'head': head, 'values': sorted_values, 'province': False}
    return render(request, 'olympiad/olympiad_result_view.html', context=context)


def olympiad_result_mmo58_second_ahlah(request):
    olympiad = {'name': 'ММО-58, Хот, Ахлах ангилал'}
    ids = [377,378,379,386,387,388]
    results = Result.objects.filter(problem_id__in=ids)
    head, sorted_values = format_results(olympiad, results, False, ids)

    context = {'olympiad': olympiad, 'head': head, 'values': sorted_values, 'province': False}
    return render(request, 'olympiad/olympiad_result_view.html', context=context)


def olympiad_result_mmo58_second_bagsh(request):
    olympiad = {'name': 'ММО-58, Хот, Багшийн ангилал'}
    ids = [380,381,382,389,390,391]
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

def format_results(olympiad, results, with_province, ids = False):
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
                row = str(contestant.last_name) + ', ' + str(contestant.first_name), contestant.id, '<a href="?p={}">{}</a>'.format(
                contestant.data.province.id, contestant.data.province.name)
            except:
                row = str(contestant.last_name) + ', ' + str(contestant.first_name), contestant.id, ''

        else:
            try:
                row = str(contestant.last_name) + ', ' + str(contestant.first_name), contestant.id, contestant.data.province.name + ', ' + contestant.data.school
            except:
                row = str(contestant.id) + ', ' + str(contestant.first_name), contestant.id, contestant.data.province.name
        try:
            grade = '<a href="?g={}">{}</a>'.format(contestant.data.grade.id,contestant.data.grade.name)
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
                    score ='<span class="text-warning">' + str(score) + '</span>'
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
            create = Result.objects.get_or_create(olympiad=olympiad,problem=problem,contestant=contestant)
            if create[1]:
                result = create[0]
                result.grader_comment = 'Системд материалаа оруулаагүй. Системээс үүсгэсэн.'
                result.save()

#duureg
def import_results():
    file = '/home/deploy/khanuul.csv'
    # file = '/Users/baysa/Documents/igo-elem-results.csv'
    with open(file) as f:
        reader = csv.reader(f)
        i=0
        for row in reader:
            i = i+1
            try:
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=int(row[1]),problem_id=int(row[2]))
                if result.score is None or result.score==0:
                    result.score = int(row[3])
                    result.grader_comment = 'Дүнгийн хүснэгтээс хуулав.'
                    result.state = 2
                    result.save()
            except:
                print(row, i)
    return True

#dund1
def import_results_2():
    file = '/home/deploy/hotd1.csv'
    # file = '/Users/baysa/Documents/hotd1.csv'
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i=0
        for row in reader:
            try:
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=68,problem_id=370)
                result.score = int(row[1])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=68,problem_id=371)
                result.score = int(row[2])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=68,problem_id=372)
                result.score = int(row[3])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=68,problem_id=373)
                result.score = int(row[4])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True

#ahlah
def import_results_3():
    file = '/home/deploy/hota2.csv'
    # file = '/Users/baysa/Documents/hota2.csv'
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i=0
        for row in reader:
            try:
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=73,problem_id=386)
                result.score = int(row[1])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=73,problem_id=387)
                result.score = int(row[2])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=73,problem_id=388)
                result.score = int(row[3])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True

#bagsh
def import_results_4():
    file = '/home/deploy/hotb2.csv'
    # file = '/Users/baysa/Documents/hotb2.csv'
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i=0
        for row in reader:
            try:
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=74,problem_id=389)
                result.score = int(row[1])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=74,problem_id=390)
                result.score = int(row[2])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=74,problem_id=391)
                result.score = int(row[3])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True

#dund2
def import_results_5():
    file = '/home/deploy/hotd21.csv'
    # file = '/Users/baysa/Documents/hotd21.csv'
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i = 0
        for row in reader:
            i = i + 1
            try:
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=69,problem_id=374)
                result.score = int(row[1])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=69,problem_id=375)
                result.score = int(row[2])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=69,problem_id=376)
                result.score = int(row[3])
                result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True

#dunduls
def import_uls_1():
    file = '/home/deploy/dunduls.csv'
    # file = '/Users/baysa/dunduls.csv'
    group = Group.objects.get(pk=15)
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i=0
        for row in reader:
            print(row)
            try:
                user = User.objects.get(pk=int(row[0]))
                group.user_set.add(user)
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=75,problem_id=404)
                result.score = int(row[1])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=75,problem_id=405)
                result.score = int(row[2])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=75,problem_id=406)
                result.score = int(row[3])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=75,problem_id=407)
                result.score = int(row[4])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=75,problem_id=408)
                result.score = int(row[5])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=75,problem_id=409)
                result.score = int(row[6])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True

#ahlauls
def import_uls_2():
    file = '/home/deploy/ahlahuls.csv'
    #file = '/Users/baysa/ahlahuls.csv'
    group = Group.objects.get(pk=16)
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i=0
        for row in reader:
            print(row)
            try:
                user = User.objects.get(pk=int(row[0]))
                group.user_set.add(user)
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=76,problem_id=410)
                result.score = int(row[1])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=76,problem_id=411)
                result.score = int(row[2])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=76,problem_id=412)
                result.score = int(row[3])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=76,problem_id=413)
                result.score = int(row[4])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=76,problem_id=414)
                result.score = int(row[5])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=76,problem_id=415)
                result.score = int(row[6])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True

#bagshuls
def import_uls_3():
    file = '/home/deploy/bagshuls.csv'
    #file = '/Users/baysa/bagshuls.csv'
    group = Group.objects.get(pk=17)
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i=0
        for row in reader:
            print(row)
            try:
                user = User.objects.get(pk=int(row[0]))
                group.user_set.add(user)
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=77,problem_id=416)
                result.score = int(row[1])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=77,problem_id=417)
                result.score = int(row[2])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=77,problem_id=418)
                result.score = int(row[3])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=77,problem_id=419)
                result.score = int(row[4])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=77,problem_id=420)
                result.score = int(row[5])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=77,problem_id=421)
                result.score = int(row[6])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True


#bagshuls
def import_igo_elem():
    file = '/Users/baysa/Documents/igo-elem-results.csv'
    file = '/home/deploy/igo-elem-results.csv'
    group = Group.objects.get(pk=17)
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i=0
        for row in reader:
            print(row)
            try:
                user = User.objects.get(pk=int(row[0]))
                group.user_set.add(user)
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=86,problem_id=446)
                result.score = int(row[1])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=86,problem_id=447)
                result.score = int(row[2])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=86,problem_id=448)
                result.score = int(row[3])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=86,problem_id=449)
                result.score = int(row[4])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=86,problem_id=450)
                result.score = int(row[5])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True

#bagshuls
def import_igo_inter():
    file = '/Users/baysa/Documents/igo-inter-results.csv'
    file = '/home/deploy/igo-inter-results.csv'
    group = Group.objects.get(pk=17)
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i=0
        for row in reader:
            print(row)
            try:
                user = User.objects.get(pk=int(row[0]))
                group.user_set.add(user)
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=87,problem_id=451)
                result.score = int(row[1])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=87,problem_id=452)
                result.score = int(row[2])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=87,problem_id=453)
                result.score = int(row[3])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=87,problem_id=454)
                result.score = int(row[4])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=87,problem_id=455)
                result.score = int(row[5])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True


#bagshuls
def import_igo_advanced():
    file = '/Users/baysa/Documents/igo-advanced-results.csv'
    file = '/home/deploy/igo-advanced-results.csv'
    group = Group.objects.get(pk=17)
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i=0
        for row in reader:
            print(row)
            try:
                user = User.objects.get(pk=int(row[0]))
                group.user_set.add(user)
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=88,problem_id=456)
                result.score = int(row[1])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=88,problem_id=457)
                result.score = int(row[2])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=88,problem_id=458)
                result.score = int(row[3])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=88,problem_id=459)
                result.score = int(row[4])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=88,problem_id=460)
                result.score = int(row[5])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
            except:
                print(row, i)

    return True


#bagshuls
def import_igo_bagsh():
    file = '/Users/baysa/Documents/igo-advanced-results.csv'
    file = '/home/deploy/igo-bagsh-results.csv'
    group = Group.objects.get(pk=17)
    with open(file, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        i=0
        for row in reader:
            print(row)
            try:
                user = User.objects.get(pk=int(row[0]))
                group.user_set.add(user)
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=89,problem_id=463)
                result.score = int(row[1])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=89,problem_id=464)
                result.score = int(row[2])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=89,problem_id=465)
                result.score = int(row[3])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=89,problem_id=466)
                result.score = int(row[4])
                if created:
                    result.state = 2
                result.grader_comment = 'Дүнгийн хүснэгт.'
                result.save()
                result, created = Result.objects.get_or_create(contestant_id=int(row[0]),olympiad_id=89,problem_id=467)
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
        print(file_extension)
        if file_extension.lower() in ['.xls','.xlsx']:
            try:
                print('5-6')
                df1 = pd.read_excel(name, '5-6', engine='openpyxl')
                num = num + importResults(df1, 90, f)
            except:
                pass
            
            try:
                print('7-8')
                df2 = pd.read_excel(name, '7-8', engine='openpyxl')
                num = num + importResults(df2, 91, f)
            except:
                pass
            
            try:
                print('9-10')
                df3 = pd.read_excel(name, '9-10', engine='openpyxl')
                num = num + importResults(df3, 92, f)
            except:
                pass
            
            try:
                print('11-12')
                df4 = pd.read_excel(name, '11-12', engine='openpyxl')
                num = num + importResults(df4, 93, f)
            except:
                pass

    return HttpResponse("<p>{} хариулт орууллаа.</p>".format(num))


def importResults(df,oid,name):
    try:
        olympiad=Olympiad.objects.get(pk=oid)
    except:
        print('No Olympiad')
        return 0

    problems = olympiad.problem_set.all()

    size = len(problems) #bodlogiin too

    for item in df.iterrows():
        ind, row = item
        try:
            id = int(row[row.keys()[1]])
            user = User.objects.get(pk=id)
        except:
            print(row[row.keys()[2]])
            user = False
        if user:
            # print(user.first_name)
            if user.first_name == '':
                user.last_name = str(row[row.keys()[2]]) + '-system'
                user.first_name = str(row[row.keys()[3]]) + '-system'
                user.save()

            i=0
            for problem in problems:
                # print(i)
                value = row[row.keys()[i+7]]
                try:
                    answer, created = Result.objects.get_or_create(problem_id=problem.id,
                                                                  olympiad_id=oid,
                                                                  contestant_id=user.id)

                    try:
                        intval = int(value)
                        answer.answer = intval
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

def createCertificate(request,quiz_id,contestant_id):
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

    TEX_ROOT = "/home/deploy/latex"
    xelatex = '/usr/bin/xelatex'
    os.chdir(TEX_ROOT)
    name='{}-{}'.format(quiz_id,contestant_id)
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

    return FileResponse(open('{}.pdf'.format(name),'rb'))
