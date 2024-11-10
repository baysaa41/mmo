from .models import Olympiad, Result, ScoreSheet
from schools.models import School
from accounts.models import UserMeta
from django.contrib.auth.models import User
import json
import math

def adjusted_int_name(number, size=2):
    name = str(number)
    while len(name) < size:
        name = '0' + name
    return name

def prepare_json_results(olympiad_id):
    results = []

    # Get all users and their results for a specific olympiad
    users = User.objects.filter(contest_results__olympiad_id=olympiad_id).distinct()

    for user in users:
        user_results = Result.objects.filter(contestant=user, olympiad_id=olympiad_id)
        total_score = sum([res.score or 0 for res in user_results])
        try:
            results.append({
                "username": user.username,
                "school": user.data.school if user.data else '',
                "province": user.data.province.name if user.data and user.data.province else '',
                "answers": [
                    {"problem_order": res.problem.order, "score": res.score or 0} for res in user_results
                ],
                "total_score": total_score
            })
        except Exception as e:
            print(e)
            continue

    olympiad = Olympiad.objects.filter(id=olympiad_id).first()
    olympiad.json_results = json.dumps(results)
    olympiad.save()
    return olympiad.json_results

def set_schools_name():
    schools = School.objects.all()
    for school in schools:
        for user in school.group.user_set.all():
            try:
                user.data.school = school.name
            except Exception as e:
                data = UserMeta.objects.create(user=user, school=school.name, province=school.province, reg_num='',mobile=0)
                print(user.username, e)
    return True


def set_scoretable(olympiad_id):
    print("setting scores...")
    results = Result.objects.filter(olympiad_id=olympiad_id)
    for result in results:
        sheet, created = ScoreSheet.objects.get_or_create(user_id=result.contestant_id, olympiad_id=olympiad_id)

        if result.score:
            setattr(sheet, f"s{result.problem.order}", result.score)

        sheet.save()
    print("setting ranking a...")
    set_ranking_a(olympiad_id)
    print("setting ranking b...")
    set_ranking_b(olympiad_id)


def set_ranking_a(olympiad_id):
    scoresheets = ScoreSheet.objects.filter(olympiad_id=olympiad_id).order_by('-total')
    ranking = 1
    current_score = None

    for index, sheet in enumerate(scoresheets, start=1):
        if current_score != sheet.total:
            ranking = index
            current_score = sheet.total
        sheet.ranking_a = ranking
        sheet.save()

def set_ranking_b(olympiad_id):
    scoresheets = ScoreSheet.objects.filter(olympiad_id=olympiad_id).order_by('total')
    lowest = len(scoresheets)
    ranking = lowest
    current_score = None

    for index, sheet in enumerate(scoresheets, start=1):
        if current_score != sheet.total:
            ranking = lowest - index + 1
            current_score = sheet.total
        sheet.ranking_b = ranking
        sheet.save()

def set_ranking_a_p(olympiad_id,province_id):
    scoresheets = ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                            user__data__province_id=province_id).order_by('-total')
    ranking = 1
    current_score = None

    for index, sheet in enumerate(scoresheets, start=1):
        if current_score != sheet.total:
            ranking = index
            current_score = sheet.total
        sheet.ranking_a_p = ranking
        sheet.save()

def set_ranking_b_p(olympiad_id,province_id):
    scoresheets = ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                            user__data__province_id=province_id).order_by('total')
    lowest = len(scoresheets)
    ranking = lowest
    current_score = None

    for index, sheet in enumerate(scoresheets, start=1):
        if current_score != sheet.total:
            ranking = lowest - index + 1
            current_score = sheet.total
        sheet.ranking_b_p = ranking
        sheet.save()
