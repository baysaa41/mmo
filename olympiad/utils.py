from .models import Olympiad, Result, ScoreSheet
from accounts.models import Province, Zone
from django.contrib.auth.models import User
import json

olympiads = [168,169,170,171,172,173]
provinces = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,24,25,27,28,29,30]
zones = [1,2,3,4,5,12]

#(olympiad,ulsiin_erh,hotiin_erh_jagsaalt,hotiin_erh,busiin_erh)
kwots = [(168,0,30,20,0),(169,0,30,20,10),(170,2,30,20,10),(171,2,30,20,10),(172,0,10,10,5),(173,2,10,10,5)]


def set_ulsiin_erh():
    for kwot in kwots:
        olympiad_id, third_kwot, city_kwot_by_order, city_kwot_by_province, zone_kwot = kwot
        #ulsiin erh
        sheets_0 = ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                             user__data__province_id__in=provinces,
                                             ranking_b_p__lte=third_kwot,
                                             ranking_b_p__gte=1)
        sheets_0.update(prizes='Улсын эрх')
        #ulsiin erh 3 duureg
        sheets_01 = ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                             user__data__province__zone_id=5,
                                             ranking_b_z__lte=third_kwot,
                                             ranking_b_z__gte=1)
        sheets_01.update(prizes='Улсын эрх')

def set_hotiin_jagsaalt_erh():
    for kwot in kwots:
        olympiad_id, third_kwot, city_kwot_by_order, city_kwot_by_province, zone_kwot = kwot
        #hotiin jagsaalt
        sheets_1 = ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                             user__data__province_id__in=[24,25,27,28,29,30],
                                             ranking_b_z__lte=city_kwot_by_order,
                                             ranking_b_z__gte=1,
                                             prizes=None)
        sheets_1.update(prizes='Хотын эрх, жагсаалт')

def set_kwots():
    ScoreSheet.objects.filter(olympiad_id__in=olympiads).update(prizes=None)
    set_ulsiin_erh()
    set_hotiin_jagsaalt_erh()

    for kwot in kwots:
        olympiad_id, third_kwot, city_kwot_by_order, city_kwot_by_province, zone_kwot = kwot


        #aimgaas bused
        sheets_2 = ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                     user__data__province_id__lte=21,
                                     ranking_b_p__lte=zone_kwot,
                                     ranking_b_p__gte=1,
                                     prizes=None)
        sheets_2.update(prizes='Бүсийн эрх')
        #3 duureg hotiin erh
        sheets_3 = ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                             user__data__province_id__in=[22,23,26],
                                             ranking_b_z__lte=city_kwot_by_province,
                                             ranking_b_z__gte=1,
                                             prizes=None)
        sheets_3.update(prizes='Хотын эрх, дүүргээс')
        for province_id in [24,25,27,28,29,30]:
            set_district_kwots(province_id)


def set_district_kwots(province_id):
    for kwot in kwots:
        olympiad_id, third_kwot, city_kwot_by_order, city_kwot_by_province, zone_kwot = kwot
        sheets = list(ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                           user__data__province_id=province_id,
                                           prizes=None).order_by('ranking_b_p'))
        for index, sheet in enumerate(sheets):
            if index < city_kwot_by_province:
                sheet.prizes='Хотын эрх, дүүргээс'
                sheet.save()
                max_total = sheet.total

        remaining_sheets = ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                           user__data__province_id=province_id,
                                           prizes=None).order_by('ranking_b_p')
        if remaining_sheets.count() > 0 and max_total == remaining_sheets[0].total:
            ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                           user__data__province_id=province_id,
                                           total=max_total).update(prizes=None)


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

def to_scoresheet(olympiad_id):
    results = Result.objects.filter(olympiad_id=olympiad_id)
    for result in results:
        ss, created = ScoreSheet.objects.get_or_create(user=result.contestant, olympiad_id=olympiad_id)
        exec(f"ss.s{result.problem.order} = {result.score or 0}")
        ss.total += result.score or 0
        ss.save()

def update_rankings_a(olympiad_id):
    """Updates rankings for each unique Olympiad."""
    olympiads = Olympiad.objects.filter(pk=olympiad_id)  # Fetch all Olympiad instances

    updates = []
    for olympiad in olympiads:
        scores = list(ScoreSheet.objects.filter(olympiad=olympiad).order_by("-total"))

        # Compute Lowest Possible Rank (Best Case)
        lowest_rank = 1  # Start ranking from 1
        prev_score = None
        score_count = 0  # Count occurrences of each score

        for i, sheet in enumerate(scores):
            if sheet.total != prev_score:
                lowest_rank += score_count  # Skip ranks for previous duplicates
                score_count = 1
            else:
                score_count += 1

            sheet.list_rank = lowest_rank + score_count - 1
            sheet.ranking_a = lowest_rank  # Assign lowest possible rank
            prev_score = sheet.total

        updates.extend(scores)

    ScoreSheet.objects.bulk_update(updates, ["ranking_a","list_rank"])

def update_rankings_a_p(olympiad_id,province_id):
    """Updates rankings for each unique Olympiad."""
    olympiads = Olympiad.objects.filter(pk=olympiad_id)  # Fetch all Olympiad instances

    updates = []
    for olympiad in olympiads:
        scores = list(ScoreSheet.objects.filter(olympiad=olympiad,user__data__province_id=province_id).order_by("-total"))

        # Compute Lowest Possible Rank (Best Case)
        lowest_rank = 1  # Start ranking from 1
        prev_score = None
        score_count = 0  # Count occurrences of each score

        for i, sheet in enumerate(scores):
            if sheet.total != prev_score:
                lowest_rank += score_count  # Skip ranks for previous duplicates
                score_count = 1
            else:
                score_count += 1

            sheet.list_rank_p = lowest_rank + score_count - 1
            sheet.ranking_a_p = lowest_rank  # Assign lowest possible rank
            prev_score = sheet.total

        updates.extend(scores)

    ScoreSheet.objects.bulk_update(updates, ["ranking_a_p","list_rank_p"])

def update_rankings_a_z(olympiad_id,zone_id):
    """Updates rankings for each unique Olympiad."""
    olympiads = Olympiad.objects.filter(pk=olympiad_id)  # Fetch all Olympiad instances

    updates = []
    for olympiad in olympiads:
        if zone_id==12:
            scores = list(ScoreSheet.objects.filter(olympiad=olympiad,user__data__province__zone_id__gt=5).order_by("-total"))
        else:
            scores = list(ScoreSheet.objects.filter(olympiad=olympiad,user__data__province__zone_id=zone_id).order_by("-total"))

        # Compute Lowest Possible Rank (Best Case)
        lowest_rank = 1  # Start ranking from 1
        prev_score = None
        score_count = 0  # Count occurrences of each score

        for i, sheet in enumerate(scores):
            if sheet.total != prev_score:
                lowest_rank += score_count  # Skip ranks for previous duplicates
                score_count = 1
            else:
                score_count += 1

            sheet.list_rank_z = lowest_rank + score_count - 1
            sheet.ranking_a_z = lowest_rank  # Assign lowest possible rank
            prev_score = sheet.total

        updates.extend(scores)

    ScoreSheet.objects.bulk_update(updates, ["ranking_a_z","list_rank_z"])

def update_rankings_b(olympiad_id):
    """Updates rankings for each unique Olympiad."""
    olympiads = Olympiad.objects.filter(pk=olympiad_id)  # Fetch all Olympiad instances

    updates = []
    for olympiad in olympiads:
        scores = list(ScoreSheet.objects.filter(olympiad=olympiad).order_by("total"))
        count = len(scores)
        # print(count)

        # Compute Lowest Possible Rank (Best Case)
        lowest_rank = 1  # Start ranking from 1
        prev_score = None
        score_count = 0  # Count occurrences of each score

        for i, sheet in enumerate(scores):
            if sheet.total != prev_score:
                lowest_rank += score_count  # Skip ranks for previous duplicates
                score_count = 1
            else:
                score_count += 1

            sheet.ranking_b = count - lowest_rank + 1
            prev_score = sheet.total

        updates.extend(scores)

    ScoreSheet.objects.bulk_update(updates, ["ranking_b"])

def update_rankings_b_p(olympiad_id,province_id):
    """Updates rankings for each unique Olympiad."""
    olympiads = Olympiad.objects.filter(pk=olympiad_id)  # Fetch all Olympiad instances

    updates = []
    for olympiad in olympiads:
        scores = list(ScoreSheet.objects.filter(olympiad=olympiad,user__data__province_id=province_id).order_by("total"))
        count = len(scores)
        # print(count)

        # Compute Lowest Possible Rank (Best Case)
        lowest_rank = 1  # Start ranking from 1
        prev_score = None
        score_count = 0  # Count occurrences of each score

        for i, sheet in enumerate(scores):
            if sheet.total != prev_score:
                lowest_rank += score_count  # Skip ranks for previous duplicates
                score_count = 1
            else:
                score_count += 1

            sheet.ranking_b_p = count - lowest_rank + 1
            prev_score = sheet.total

        updates.extend(scores)

    ScoreSheet.objects.bulk_update(updates, ["ranking_b_p"])

def update_rankings_b_z(olympiad_id,zone_id):
    """Updates rankings for each unique Olympiad."""
    olympiads = Olympiad.objects.filter(pk=olympiad_id)  # Fetch all Olympiad instances

    updates = []
    for olympiad in olympiads:
        if zone_id==12:
            scores = list(ScoreSheet.objects.filter(olympiad=olympiad,user__data__province__zone_id__gt=5).order_by("total"))
        else:
            scores = list(ScoreSheet.objects.filter(olympiad=olympiad,user__data__province__zone_id=zone_id).order_by("total"))
        count = len(scores)
        # print(count)

        # Compute Lowest Possible Rank (Best Case)
        lowest_rank = 1  # Start ranking from 1
        prev_score = None
        score_count = 0  # Count occurrences of each score

        for i, sheet in enumerate(scores):
            if sheet.total != prev_score:
                lowest_rank += score_count  # Skip ranks for previous duplicates
                score_count = 1
            else:
                score_count += 1

            sheet.ranking_b_z = count - lowest_rank + 1
            prev_score = sheet.total

        updates.extend(scores)

    ScoreSheet.objects.bulk_update(updates, ["ranking_b_z"])

#sets rankings
def update_all():
    for olympiad in olympiads:
        update_rankings_a(olympiad)
        update_rankings_b(olympiad)
        for province in provinces:
            update_rankings_a_p(olympiad,province)
            update_rankings_b_p(olympiad,province)
        for zone in zones:
            update_rankings_a_z(olympiad,zone)
            update_rankings_b_z(olympiad,zone)