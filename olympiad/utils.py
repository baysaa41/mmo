from .models import Olympiad, Result, ScoreSheet
from django.contrib.auth.models import User
import json

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
