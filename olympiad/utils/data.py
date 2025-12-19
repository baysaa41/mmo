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

    # 2. Одоо байгаа ScoreSheet-үүдийг олох
    existing_sheets = {
        sheet.user_id: sheet
        for sheet in ScoreSheet.objects.filter(olympiad_id=olympiad_id)
    }

    to_create = []
    to_update = []

    # 3. Оролцогч тус бүрээр нь үр дүнг бүлэглэх
    for contestant_id, results_group in groupby(all_results, key=lambda r: r.contestant_id):
        results_list = list(results_group)
        contestant = results_list[0].contestant

        # UserMeta шалгах ба шаардлагатай бол үүсгэх
        if not hasattr(contestant, 'data') or contestant.data is None:
            # UserMeta үүсгэх (хамгийн суурь мэдээллээр)
            from accounts.models import UserMeta
            try:
                UserMeta.objects.create(
                    user=contestant,
                    reg_num='',  # default утга
                )
                # Дахин уншиж авах (relation cache шинэчлэх)
                contestant.refresh_from_db()
                print(f"⚠️ {contestant.id} ({contestant.username}): UserMeta үүсгэв")
            except Exception as e:
                print(f"❌ {contestant.id} ({contestant.username}): UserMeta үүсгэх алдаа - {e}")
                continue

        school_obj = contestant.data.school

        # Онооны талбаруудыг тэглэх
        score_data = {f's{i}': 0 for i in range(1, 21)}

        for result in results_list:
            if result.score is not None and result.problem:
                score_data[f's{result.problem.order}'] = result.score

        # Нийт оноог тооцоолох
        total = sum(score_data.values())

        if contestant_id in existing_sheets:
            # Update existing
            sheet = existing_sheets[contestant_id]
            sheet.school = school_obj
            sheet.total = total
            for key, value in score_data.items():
                setattr(sheet, key, value)
            to_update.append(sheet)
        else:
            # Create new
            to_create.append(ScoreSheet(
                user_id=contestant_id,
                olympiad_id=olympiad_id,
                school=school_obj,
                total=total,
                **score_data
            ))

    # 4. Bulk operations
    if to_create:
        ScoreSheet.objects.bulk_create(to_create, batch_size=1000)

    if to_update:
        update_fields = ['school', 'total'] + [f's{i}' for i in range(1, 21)]
        ScoreSheet.objects.bulk_update(to_update, update_fields, batch_size=1000)