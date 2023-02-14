from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from olympiad.models import Olympiad, Result, SchoolYear
from accounts.models import Province, UserMeta
from django.forms import modelformset_factory
from .forms import ResultsForm
import pandas as pd
from django.db import connection
from django.contrib.auth.models import User, Group

ResultsFormSet = modelformset_factory(Result, form=ResultsForm, extra=0)


def results_first_round(request):
    level_id = request.GET.get('level_id', 4)
    if int(level_id) == 4:
        olympiad_one = 8
        olympiad_two = 10
    else:
        olympiad_one = 9
        olympiad_two = 11
    province_id = request.GET.get('province_id', 0)

    if int(province_id) > 0:
        province = Province.objects.get(pk=province_id)
    else:
        province = Province(name='Улаанбаатар')

    if province_id == 0:
        with connection.cursor() as cursor:
            cursor.execute("create temporary table tmp_table1 select u.id, u.last_name, u.first_name, prov.`name` \
            as province, m.school, g.name as grade, sum(r.score) total \
            from olympiad_result r join auth_user u on r.`contestant_id`=u.id join accounts_usermeta m on u.id=m.user_id \
            join accounts_province prov on prov.id=m.`province_id` join accounts_grade g on g.id=m.grade_id \
            where (r.olympiad_id=%s or r.olympiad_id=%s) and m.province_id>21 \
             group by u.id order by total desc, id asc", [olympiad_one, olympiad_two])
            cursor.execute("set @row_num=0")
            cursor.execute(
                "create temporary table tmp_table2 select t4.*,(@row_num:=@row_num+1) as rk from tmp_table1 t4")
            cursor.execute(
                "create temporary table tmp_rank select total, min(rk) as rank from tmp_table2 group by total")
            cursor.execute("select id, last_name, first_name, province, school, grade, t1.total, rank  \
                from tmp_table2 t1 join tmp_rank t2 on t1.total=t2.total where t1.total>0 or true")
            results = cursor.fetchall()
            # for result in results:
            #    if result[7] < 31:
            #        award=Award.objects.get_or_create(contestant_id=result[0],olympiad_id=olympiad_two,grade_id=level_id,place='II шат')

    else:
        with connection.cursor() as cursor:
            cursor.execute("create temporary table tmp_table1 select u.id, u.last_name, u.first_name, prov.`name` \
            as province, m.school, g.name as grade, sum(r.score) total \
            from olympiad_result r join auth_user u on r.`contestant_id`=u.id join accounts_usermeta m on u.id=m.user_id \
            join accounts_province prov on prov.id=m.`province_id` join accounts_grade g on g.id=m.grade_id \
            where (r.olympiad_id=%s or r.olympiad_id=%s) and m.`province_id`=%s \
            group by u.id order by total desc, id asc", [olympiad_one, olympiad_two, province_id])
            cursor.execute("set @row_num=0")
            cursor.execute(
                "create temporary table tmp_table2 select t4.*,(@row_num:=@row_num+1) as rk from tmp_table1 t4")
            cursor.execute(
                "create temporary table tmp_rank select total, min(rk) as rank from tmp_table2 group by total")
            cursor.execute("select id, last_name, first_name, province, school, grade, t1.total, rank  \
                from tmp_table2 t1 join tmp_rank t2 on t1.total=t2.total where t1.total>0 or true")
            results = cursor.fetchall()
            # for result in results:
            #    if int(province_id)>21:
            #        min_score = 2
            #        max_place = 5
            #    else:
            #        min_score = 1
            #        max_place = 10
            #    if (int(result[7]) <= max_place) and (int(result[6]) >= min_score):
            #        award=Award.objects.get_or_create(contestant_id=result[0],olympiad_id=olympiad_two,grade_id=level_id,place='II шат')

    return render(request, 'olympiad/results_first.html', {'results': results, 'province': province})

def results_second_round(request):
    level_id = request.GET.get('level_id', 4)
    if int(level_id) == 4:
        olympiad_one = 12
        olympiad_two = 14
    else:
        olympiad_one = 13
        olympiad_two = 15
    province_id = request.GET.get('province_id', 0)

    if int(province_id) > 0:
        province = Province.objects.get(pk=province_id)
    else:
        province = Province(name='II шат, Улаанбаатар хот')

    if province_id == 0:
        with connection.cursor() as cursor:
            cursor.execute("SET GLOBAL sql_mode=(SELECT REPLACE(@@sql_mode,'ONLY_FULL_GROUP_BY',''))")
            cursor.execute("create temporary table tmp_table1 select u.id, u.last_name, u.first_name, prov.`name` \
            as province, m.school, g.name as grade, sum(r.score) as total, m.mobile, u.email, aug.group_id as grp \
            from olympiad_result r join auth_user u on r.`contestant_id`=u.id join accounts_usermeta m on u.id=m.user_id \
            join accounts_province prov on prov.id=m.`province_id` join accounts_grade g on g.id=m.grade_id \
            left join auth_user_groups aug on u.id = aug.user_id and aug.group_id=3\
            where (r.olympiad_id=%s or r.olympiad_id=%s) and m.province_id>21 \
             group by u.id order by total desc, id asc", [olympiad_one, olympiad_two])
            cursor.execute("set @row_num=0")
            cursor.execute(
                "create temporary table tmp_table2 select t4.*,(@row_num:=@row_num+1) as rk from tmp_table1 t4")
            cursor.execute(
                "create temporary table tmp_rank select total, min(rk) as rank from tmp_table2 group by total")
            cursor.execute("select id, last_name, first_name, province, school, grade, t1.total, rank, mobile, email, t1.grp  \
                from tmp_table2 t1 join tmp_rank t2 on t1.total=t2.total order by rank, grade")
            results = cursor.fetchall()
            # for result in results:
            #    if result[7] < 31:
            #        award=Award.objects.get_or_create(contestant_id=result[0],olympiad_id=olympiad_two,grade_id=level_id,place='II шат')

    else:
        with connection.cursor() as cursor:
            cursor.execute("SET GLOBAL sql_mode=(SELECT REPLACE(@@sql_mode,'ONLY_FULL_GROUP_BY',''))")
            cursor.execute("create temporary table tmp_table1 select u.id, u.last_name, u.first_name, prov.`name` \
            as province, m.school, g.name as grade, sum(r.score) total, m.mobile, u.email, aug.group_id as grp \
            from olympiad_result r join auth_user u on r.`contestant_id`=u.id join accounts_usermeta m on u.id=m.user_id \
            join accounts_province prov on prov.id=m.`province_id` join accounts_grade g on g.id=m.grade_id \
            left join auth_user_groups aug on u.id = aug.user_id and aug.group_id=3 \
            where (r.olympiad_id=%s or r.olympiad_id=%s) and m.`province_id`=%s \
            group by u.id order by total desc, id asc", [olympiad_one, olympiad_two, province_id])
            cursor.execute("set @row_num=0")
            cursor.execute(
                "create temporary table tmp_table2 select t4.*,(@row_num:=@row_num+1) as rk from tmp_table1 t4")
            cursor.execute(
                "create temporary table tmp_rank select total, min(rk) as rank, grp from tmp_table2 group by total")
            cursor.execute("select id, last_name, first_name, province, school, grade, t1.total, rank, mobile, email, t1.grp  \
                from tmp_table2 t1 join tmp_rank t2 on t1.total=t2.total order by rank, grade")
            results = cursor.fetchall()
            # for result in results:
            #    if int(province_id)>21:
            #        min_score = 2
            #        max_place = 5
            #    else:
            #        min_score = 1
            #        max_place = 10
            #    if (int(result[7]) <= max_place) and (int(result[6]) >= min_score):
            #        award=Award.objects.get_or_create(contestant_id=result[0],olympiad_id=olympiad_two,grade_id=level_id,place='II шат')

    return render(request, 'olympiad/results_second.html', {'results': results, 'province': province})

@login_required
def add_to_third(request):
    user_id = int(request.GET.get('user_id', 0))
    group_id = int(request.GET.get('group_id', 0))
    if request.user.is_staff:
        user = User.objects.filter(pk=user_id).first()
        group = Group.objects.filter(pk=group_id).first()
        if user and group:
            user.groups.add(group_id)
            return JsonResponse({'status': 1})
    return JsonResponse({'status': 0})

def results_second_round_all(request):
    level_id = request.GET.get('level_id', 4)
    if int(level_id) == 4:
        olympiad_one = 12
        olympiad_two = 14
    else:
        olympiad_one = 13
        olympiad_two = 15

    with connection.cursor() as cursor:
        cursor.execute("create temporary table tmp_table1 select u.id, u.last_name, u.first_name, prov.`name` \
        as province, m.school, g.name as grade, sum(r.score) total, m.mobile, u.email \
        from olympiad_result r join auth_user u on r.`contestant_id`=u.id join accounts_usermeta m on u.id=m.user_id \
        join accounts_province prov on prov.id=m.`province_id` join accounts_grade g on g.id=m.grade_id \
        where (r.olympiad_id=%s or r.olympiad_id=%s) \
         group by u.id order by total desc, id asc", [olympiad_one, olympiad_two])
        cursor.execute("set @row_num=0")
        cursor.execute(
            "create temporary table tmp_table2 select t4.*,(@row_num:=@row_num+1) as rk from tmp_table1 t4")
        cursor.execute(
            "create temporary table tmp_rank select total, min(rk) as rank from tmp_table2 group by total")
        cursor.execute("select id, last_name, first_name, province, school, grade, t1.total, rank, mobile, email  \
            from tmp_table2 t1 join tmp_rank t2 on t1.total=t2.total where t1.total>0 or true")
        results = cursor.fetchall()

    province = {'name': 'II шатны шалгаруулалт'}

    return render(request, 'olympiad/results_second.html', {'results': results, 'province': province})


def second_round_contestans(request):
    group = Group.objects.get(pk=2)
    students = group.user_set.all().order_by('data__province_id', 'data__school', 'data__grade_id')
    return render(request, 'olympiad/second_round_contestants.html', {'students': students, 'title':
        'II шатны шалгаруулалтад тэнцсэн сурагчдын жагсаалт:'})

def third_round_contestans(request):
    group = Group.objects.get(pk=3)
    level_id = int(request.GET.get('level_id', 0))

    if level_id == 4:
        students = group.user_set.filter(data__level_id=level_id).order_by('data__province_id', 'data__school',
                                                                           'data__grade_id')
        title = 'ММО-57 шалгарсан сурагчид, Дунд ангилал'
    elif level_id == 5:
        students = group.user_set.filter(data__level_id=level_id).order_by('data__province_id', 'data__school',
                                                                           'data__grade_id')
        title = 'ММО-57 шалгарсан сурагчид, Ахлах ангилал'
    else:
        students = group.user_set.all().order_by('data__province_id', 'data__school', 'data__grade_id')
        title = 'ММО-57 шалгарсан сурагчид'

    return render(request, 'olympiad/third_round_contestants.html', {'students': students, 'title': title})

def two_days_junior(request):
    with connection.cursor() as cursor:
        cursor.execute("SET GLOBAL sql_mode=(SELECT REPLACE(@@sql_mode,'ONLY_FULL_GROUP_BY',''))")
        cursor.execute("create temporary table junior_first select u.id, u.first_name, p.name province, p.id province_id, \
            sum(r.score) total, oa.place from olympiad_result r join auth_user u on r.`contestant_id`=u.id \
            join accounts_usermeta m on m.user_id=u.id join accounts_province p on p.id=m.province_id \
            left join olympiad_award oa on u.id = oa.contestant_id where r.olympiad_id=8 group by u.id")
        cursor.execute("create temporary table junior_second select u.id, u.first_name, p.name province, p.id province_id, \
            sum(r.score) total, oa.place from olympiad_result r join auth_user u on r.`contestant_id`=u.id \
            join accounts_usermeta m on m.user_id=u.id join accounts_province p on p.id=m.province_id \
            left join olympiad_award oa on u.id = oa.contestant_id where r.olympiad_id=10 group by u.id")
        cursor.execute("select f.id, f.first_name, f.province, f.total secondd, s.total firstd, \
                       f.total + COALESCE(s.total,0) total, COALESCE(f.place,'') from junior_second f \
                       left join junior_first s on f.id=s.id where f.province_id>0 order by f.province_id, total desc")
        results = cursor.fetchall()

    return render(request, 'olympiad/two_days.html', {'results': results, 'title': 'Дунд ангилал', 'olympiad': 8})

def two_days_senior(request):
    with connection.cursor() as cursor:
        cursor.execute("SET GLOBAL sql_mode=(SELECT REPLACE(@@sql_mode,'ONLY_FULL_GROUP_BY',''))")
        cursor.execute("create temporary table junior_first select u.id, u.first_name, p.name province, p.id province_id, \
            sum(r.score) total, oa.place from olympiad_result r join auth_user u on r.`contestant_id`=u.id \
            join accounts_usermeta m on m.user_id=u.id join accounts_province p on p.id=m.province_id \
            left join olympiad_award oa on u.id = oa.contestant_id where r.olympiad_id=9 group by u.id")
        cursor.execute("create temporary table junior_second select u.id, u.first_name, p.name province, p.id province_id, \
            sum(r.score) total, oa.place from olympiad_result r join auth_user u on r.`contestant_id`=u.id \
            join accounts_usermeta m on m.user_id=u.id join accounts_province p on p.id=m.province_id \
            left join olympiad_award oa on u.id = oa.contestant_id where r.olympiad_id=11 group by u.id")
        cursor.execute("select f.id, f.first_name, f.province, f.total secondd, s.total firstd, \
                       f.total + COALESCE(s.total,0) total, COALESCE(f.place,'') from junior_second f \
                       left join junior_first s on f.id=s.id where f.province_id>0 order by f.province_id, total desc")
        results = cursor.fetchall()

    return render(request, 'olympiad/two_days.html', {'results': results, 'title': 'Ахлах ангилал', 'olympiad': 9})

def imo_results(request):
    cutoffs = [6, 0, 0]
    ids = [16, 17, 18, 19, 21, 23]
    headers = get_imo_headers(ids)
    results = get_imo_results(ids, cutoffs)
    body = format_results(results)
    text_content = "<h3>IMO-62 сонгон шалгаруулалт</h3><table class='table table-bordered'>\n{}\n{}\n</table>".format(
        headers, body)
    return render(request, 'base.html', {'text_content': text_content})

def mmo57_dund_results(request):
    cutoffs = [1, 4, 14]
    ids = [20, 22]
    headers = get_imo_headers(ids)
    results = get_mmo_results(ids, 4, cutoffs)
    body = format_results(results)
    text_content = "<h3>ММО-57 дунд ангиллын дүн</h3><table class='table table-bordered'>\n{}\n{}\n</table>".format(
        headers, body)
    return render(request, 'base.html', {'text_content': text_content})

def mmo57_ahlah_results(request):
    cutoffs = [1, 5, 14]
    ids = [21, 23]
    headers = get_imo_headers(ids)
    results = get_mmo_results(ids, 5, cutoffs)
    body = format_results(results)
    text_content = "<h3>ММО-57 ахлах ангиллын дүн</h3><table class='table table-bordered'>\n{}\n{}\n</table>".format(
        headers, body)
    return render(request, 'base.html', {'text_content': text_content})

def get_imo_headers(ids):
    header = "<tr><th rowspan='2'>№</th><th rowspan='2'>Овог, нэр</th>"
    header = header + "<th rowspan='2'>Аймаг/Дүүрэг</th><th rowspan='2'>Сургууль</th>"
    second_row = "<tr>"
    for id in ids:
        olympiad = Olympiad.objects.get(pk=id)
        count = olympiad.problem_set.count()
        header = header + "<th colspan='{}'>{}</th>".format(count, olympiad.name)
        problems = olympiad.problem_set.all()
        for problem in problems:
            second_row = second_row + '<th>{}</th>'.format(problem.order)
    header = header + "<th rowspan='2'>Нийт</th><th rowspan='2'>Шагнал</th></tr>\n"
    second_row = second_row + "</tr>\n"

    return (header + second_row)

def igo_results(request, level_id):
    if level_id == 3:
        ids = [246, 247, 282, 283]
    elif level_id == 4:
        ids = [232, 236, 274, 275]
    elif level_id == 5:
        ids = [229, 230, 265, 266]
    else:
        ids = [0, 0, 0, 0]
    pd.options.display.float_format = '{:,.2f}'.format

    with connection.cursor() as cursor:
        cursor.execute("select concat(pr.name,', ',u.first_name,', ',u.last_name,', ',u.id,', ',m.mobile), p.`id`, r.score, r.answer, u.id \
            from olympiad_result r \
            join auth_user u on r.`contestant_id`=u.id \
            join accounts_usermeta m on m.user_id=u.id \
            join accounts_province pr on m.province_id=pr.id \
            join olympiad_problem p on r.`problem_id`=p.id \
            where r.problem_id=%s or r.problem_id=%s or r.problem_id=%s or r.problem_id=%s", ids)
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

def get_imo_results(ids, cutoffs):
    students = Group.objects.get(pk=1).user_set.all()
    items = []
    for student in students:
        item = {
            'name': "{}, {}".format(student.last_name, student.first_name),
            'province': "{}".format(student.data.province.name),
            'school': "{}".format(student.data.school),
            'grade': "{}".format(student.data.grade.name),
            'results': None,
            'total': 0.0,
        }
        student_results = []
        for id in ids:
            results = Result.objects.filter(olympiad_id=id, contestant=student).order_by('problem__order')
            if not results:
                size = Olympiad.objects.get(pk=id).problem_set.count()
                for i in range(size):
                    student_results.append((0.0, 0))
            for result in results:
                if result.score != None:
                    item['total'] = item['total'] + result.score

                if result.score == None:
                    result.score = '---'
                student_results.append((result.score, result.state))
        item['results'] = student_results
        items.append(item)

    return sort_results(items, cutoffs, ['IMO-62', '', ''])

def get_mmo_results(ids, level_id, cutoffs):
    students = Group.objects.get(pk=3).user_set.all()  # .user_set.filter(data__level_id=level_id)
    items = []
    for student in students:
        item = {
            'name': "{}, {}".format(student.last_name, student.first_name),
            'province': "{}".format(student.data.province.name),
            'school': "{}".format(student.data.school),
            'grade': "{}".format(student.data.grade.name),
            'results': None,
            'total': 0.0,
        }
        student_results = []
        for id in ids:
            results = Result.objects.filter(olympiad_id=id, contestant=student,
                                            problem__olympiad__level_id=level_id).order_by('problem__order')
            if not results:
                size = Olympiad.objects.get(pk=id).problem_set.count()
                for i in range(size):
                    student_results.append((0.0, 0))
            for result in results:
                if result.score != None:
                    item['total'] = item['total'] + result.score

                if result.score == None:
                    result.score = '---'
                student_results.append((result.score, result.state))
        item['results'] = student_results
        items.append(item)

    return sort_results(items, cutoffs)

def format_results(results):
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
