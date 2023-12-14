from django.http import HttpResponse, JsonResponse, FileResponse
from django.shortcuts import render, redirect, reverse
import pandas as pd
from django.db import connection
from django.contrib.admin.views.decorators import staff_member_required

from accounts.models import Province


def get_school_names():
    with connection.cursor() as cursor:
        cursor.execute("select m.province_id, p.name, m.school, count(distinct m.user_id) count \
                       from accounts_usermeta m join olympiad_result r \
                       on m.user_id = r.contestant_id join accounts_province p on m.province_id = p.id \
                       where r.olympiad_id between 133 and 136 group by m.province_id, m.school order by count desc")
        results = cursor.fetchall()
    school_names = []
    for row in results:
        id, destrict, school, count = row
        if count > 10:
           school_names.append((id, school))
    return school_names

def get_school_results(province_id, school):
    with connection.cursor() as cursor:
        cursor.execute("select m.user_id, l.name, round(sum(r.score)*10,1) score \
                       from accounts_usermeta m join olympiad_result r \
                       on m.user_id = r.contestant_id join accounts_province p on m.province_id = p.id \
                       join accounts_level l on m.level_id = l.id \
                       where r.olympiad_id between 133 and 134 and m.province_id =%s and m.school=%s group by m.user_id ",[province_id,school])
        results_cd = cursor.fetchall()
        cursor.execute("select m.user_id, l.name, round(sum(r.score)*100/12,1) score \
                       from accounts_usermeta m join olympiad_result r \
                       on m.user_id = r.contestant_id join accounts_province p on m.province_id = p.id \
                       join accounts_level l on m.level_id = l.id \
                       where r.olympiad_id between 135 and 136 and m.province_id =%s and m.school=%s group by m.user_id ",[province_id,school])
        results_ef = cursor.fetchall()
        results = results_cd + results_ef
        results = sorted(results, key=lambda x: x[2], reverse=True)[:10]
        total = 0
        for result in results:
            total = total + result[2]

        # (student_id, student_score) x 10, total_school_score
    return results, round(total, 2)

@staff_member_required()
def index(request):
    schools = get_school_names()
    data_frames = list()
    final = list()
    for school in schools:
        province_id, school_name = school
        province = Province.objects.get(pk=province_id)
        results, total = get_school_results(province_id, school_name)
        final.append((province_id, province.name, school_name, results, total))
    sorted_final = sorted(final, key=lambda x: x[4], reverse=True)

    context = {
        'results': sorted_final
    }

    return render(request,'olympiad/beltgel2023/index.html', context)