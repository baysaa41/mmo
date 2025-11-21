from ..models import Olympiad, Result, ScoreSheet
from django.contrib.auth.models import User
import json
from itertools import groupby


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
    """
    Generates or updates ScoreSheets from Results.
    This version is highly optimized to reduce database queries.
    """
    # 1. Шаардлагатай бүх Result-ийг нэг дор татах
    all_results = Result.objects.filter(olympiad_id=olympiad_id, contestant_id__isnull=False).select_related(
        'contestant__data', 'problem'
    ).order_by('contestant_id')

    # 2. Оролцогч тус бүрээр нь үр дүнг бүлэглэх
    for contestant_id, results_group in groupby(all_results, key=lambda r: r.contestant_id):
        results_list = list(results_group)
        contestant = results_list[0].contestant

        # --- ADDED CHECK ---
        # Skip user if they don't have a UserMeta (data) profile
        if not hasattr(contestant, 'data') or contestant.data is None:
            print(f"{contestant.id} хэрэглэгчийн бүртгэлийн мэдээлэл дутуу тул алгаслаа.")
            continue

        school_obj = contestant.data.school

        # Зөвхөн албан ёсоор оролцсон сургуулийн сурагчдыг оруулах
        if not school_obj or not getattr(school_obj, 'is_official_participation', False):
            continue

        score_fields = {'school': school_obj}
        # Онооны талбаруудыг тэглэх (21 гэж хатуу бичихийн оронд)
        for i in range(1, 21):
            score_fields[f's{i}'] = 0

        for result in results_list:
            if result.score is not None and result.problem:
                score_fields[f's{result.problem.order}'] = result.score

        ScoreSheet.objects.update_or_create(
            user_id=contestant_id,
            olympiad_id=olympiad_id,
            defaults=score_fields
        )