from ..models import Olympiad, Result, ScoreSheet
from django.db.models import Window, F
from django.db.models.functions import DenseRank, RowNumber


def update_rankings_a(olympiad_id):
    """Updates rankings for each unique Olympiad using Window functions."""
    # Бүх scoresheet-ийг нэг query-ээр авч, эрэмбийг тооцоолох
    scores = list(ScoreSheet.objects.filter(olympiad_id=olympiad_id).order_by("-total"))

    if not scores:
        return

    # Python дээр эрэмбэ тооцоолох (bulk_update-д бэлтгэх)
    lowest_rank = 1
    prev_score = None
    score_count = 0

    for sheet in scores:
        if sheet.total != prev_score:
            lowest_rank += score_count
            score_count = 1
        else:
            score_count += 1

        sheet.list_rank = lowest_rank + score_count - 1
        sheet.ranking_a = lowest_rank
        prev_score = sheet.total

    ScoreSheet.objects.bulk_update(scores, ["ranking_a", "list_rank"], batch_size=2000)

def update_rankings_a_p(olympiad_id, province_id):
    """Updates rankings for province - official only."""
    scores = list(ScoreSheet.objects.filter(
        olympiad_id=olympiad_id,
        user__data__province_id=province_id,
        is_official=True
    ).order_by("-total"))

    if not scores:
        return

    lowest_rank = 1
    prev_score = None
    score_count = 0

    for sheet in scores:
        if sheet.total != prev_score:
            lowest_rank += score_count
            score_count = 1
        else:
            score_count += 1

        sheet.list_rank_p = lowest_rank + score_count - 1
        sheet.ranking_a_p = lowest_rank
        prev_score = sheet.total

    ScoreSheet.objects.bulk_update(scores, ["ranking_a_p", "list_rank_p"], batch_size=2000)

def update_rankings_a_p_all(olympiad_id, province_id):
    """Updates rankings for province - all students."""
    scores = list(ScoreSheet.objects.filter(
        olympiad_id=olympiad_id,
        user__data__province_id=province_id
    ).order_by("-total"))

    if not scores:
        return

    lowest_rank = 1
    prev_score = None
    score_count = 0

    for sheet in scores:
        if sheet.total != prev_score:
            lowest_rank += score_count
            score_count = 1
        else:
            score_count += 1

        sheet.list_rank_p_all = lowest_rank + score_count - 1
        sheet.ranking_a_p_all = lowest_rank
        prev_score = sheet.total

    ScoreSheet.objects.bulk_update(scores, ["ranking_a_p_all", "list_rank_p_all"], batch_size=2000)

def update_rankings_a_p_u(olympiad_id, province_id):
    """Updates rankings for province - unofficial only."""
    scores = list(ScoreSheet.objects.filter(
        olympiad_id=olympiad_id,
        user__data__province_id=province_id,
        is_official=False
    ).order_by("-total"))

    if not scores:
        return

    lowest_rank = 1
    prev_score = None
    score_count = 0

    for sheet in scores:
        if sheet.total != prev_score:
            lowest_rank += score_count
            score_count = 1
        else:
            score_count += 1

        sheet.list_rank_p_u = lowest_rank + score_count - 1
        sheet.ranking_a_p_u = lowest_rank
        prev_score = sheet.total

    ScoreSheet.objects.bulk_update(scores, ["ranking_a_p_u", "list_rank_p_u"], batch_size=2000)

def update_rankings_a_z(olympiad_id, zone_id):
    """Updates rankings for zone - official only."""
    scores = list(ScoreSheet.objects.filter(
        olympiad_id=olympiad_id,
        user__data__province__zone_id=zone_id,
        is_official=True
    ).order_by("-total"))

    if not scores:
        return

    lowest_rank = 1
    prev_score = None
    score_count = 0

    for sheet in scores:
        if sheet.total != prev_score:
            lowest_rank += score_count
            score_count = 1
        else:
            score_count += 1

        sheet.list_rank_z = lowest_rank + score_count - 1
        sheet.ranking_a_z = lowest_rank
        prev_score = sheet.total

    ScoreSheet.objects.bulk_update(scores, ["ranking_a_z", "list_rank_z"], batch_size=2000)

def update_rankings_a_z_all(olympiad_id, zone_id):
    """Updates rankings for zone - all students."""
    scores = list(ScoreSheet.objects.filter(
        olympiad_id=olympiad_id,
        user__data__province__zone_id=zone_id
    ).order_by("-total"))

    if not scores:
        return

    lowest_rank = 1
    prev_score = None
    score_count = 0

    for sheet in scores:
        if sheet.total != prev_score:
            lowest_rank += score_count
            score_count = 1
        else:
            score_count += 1

        sheet.list_rank_z_all = lowest_rank + score_count - 1
        sheet.ranking_a_z_all = lowest_rank
        prev_score = sheet.total

    ScoreSheet.objects.bulk_update(scores, ["ranking_a_z_all", "list_rank_z_all"], batch_size=2000)

def update_rankings_a_z_u(olympiad_id, zone_id):
    """Updates rankings for zone - unofficial only."""
    scores = list(ScoreSheet.objects.filter(
        olympiad_id=olympiad_id,
        user__data__province__zone_id=zone_id,
        is_official=False
    ).order_by("-total"))

    if not scores:
        return

    lowest_rank = 1
    prev_score = None
    score_count = 0

    for sheet in scores:
        if sheet.total != prev_score:
            lowest_rank += score_count
            score_count = 1
        else:
            score_count += 1

        sheet.list_rank_z_u = lowest_rank + score_count - 1
        sheet.ranking_a_z_u = lowest_rank
        prev_score = sheet.total

    ScoreSheet.objects.bulk_update(scores, ["ranking_a_z_u", "list_rank_z_u"], batch_size=2000)

def update_rankings_b(olympiad_id):
    """Updates rankings_b (reverse ranking)."""
    scores = list(ScoreSheet.objects.filter(olympiad_id=olympiad_id).order_by("total"))

    if not scores:
        return

    count = len(scores)
    lowest_rank = 1
    prev_score = None
    score_count = 0

    for sheet in scores:
        if sheet.total != prev_score:
            lowest_rank += score_count
            score_count = 1
        else:
            score_count += 1

        sheet.ranking_b = count - lowest_rank + 1
        prev_score = sheet.total

    ScoreSheet.objects.bulk_update(scores, ["ranking_b"], batch_size=2000)

def update_rankings_b_p(olympiad_id, province_id):
    """Updates rankings_b_p for province - official only."""
    scores = list(ScoreSheet.objects.filter(
        olympiad_id=olympiad_id,
        user__data__province_id=province_id,
        is_official=True
    ).order_by("total"))

    if not scores:
        return

    count = len(scores)
    lowest_rank = 1
    prev_score = None
    score_count = 0

    for sheet in scores:
        if sheet.total != prev_score:
            lowest_rank += score_count
            score_count = 1
        else:
            score_count += 1

        sheet.ranking_b_p = count - lowest_rank + 1
        prev_score = sheet.total

    ScoreSheet.objects.bulk_update(scores, ["ranking_b_p"], batch_size=2000)

def update_rankings_b_p_all(olympiad_id, province_id):
    """Updates rankings_b_p_all for province - all students."""
    scores = list(ScoreSheet.objects.filter(
        olympiad_id=olympiad_id,
        user__data__province_id=province_id
    ).order_by("total"))

    if not scores:
        return

    count = len(scores)
    lowest_rank = 1
    prev_score = None
    score_count = 0

    for sheet in scores:
        if sheet.total != prev_score:
            lowest_rank += score_count
            score_count = 1
        else:
            score_count += 1

        sheet.ranking_b_p_all = count - lowest_rank + 1
        prev_score = sheet.total

    ScoreSheet.objects.bulk_update(scores, ["ranking_b_p_all"], batch_size=2000)

def update_rankings_b_p_u(olympiad_id, province_id):
    """Updates rankings_b_p_u for province - unofficial only."""
    scores = list(ScoreSheet.objects.filter(
        olympiad_id=olympiad_id,
        user__data__province_id=province_id,
        is_official=False
    ).order_by("total"))

    if not scores:
        return

    count = len(scores)
    lowest_rank = 1
    prev_score = None
    score_count = 0

    for sheet in scores:
        if sheet.total != prev_score:
            lowest_rank += score_count
            score_count = 1
        else:
            score_count += 1

        sheet.ranking_b_p_u = count - lowest_rank + 1
        prev_score = sheet.total

    ScoreSheet.objects.bulk_update(scores, ["ranking_b_p_u"], batch_size=2000)

def update_rankings_b_z(olympiad_id, zone_id):
    """Updates rankings_b_z for zone - official only."""
    scores = list(ScoreSheet.objects.filter(
        olympiad_id=olympiad_id,
        user__data__province__zone_id=zone_id,
        is_official=True
    ).order_by("total"))

    if not scores:
        return

    count = len(scores)
    lowest_rank = 1
    prev_score = None
    score_count = 0

    for sheet in scores:
        if sheet.total != prev_score:
            lowest_rank += score_count
            score_count = 1
        else:
            score_count += 1

        sheet.ranking_b_z = count - lowest_rank + 1
        prev_score = sheet.total

    ScoreSheet.objects.bulk_update(scores, ["ranking_b_z"], batch_size=2000)

def update_rankings_b_z_all(olympiad_id, zone_id):
    """Updates rankings_b_z_all for zone - all students."""
    scores = list(ScoreSheet.objects.filter(
        olympiad_id=olympiad_id,
        user__data__province__zone_id=zone_id
    ).order_by("total"))

    if not scores:
        return

    count = len(scores)
    lowest_rank = 1
    prev_score = None
    score_count = 0

    for sheet in scores:
        if sheet.total != prev_score:
            lowest_rank += score_count
            score_count = 1
        else:
            score_count += 1

        sheet.ranking_b_z_all = count - lowest_rank + 1
        prev_score = sheet.total

    ScoreSheet.objects.bulk_update(scores, ["ranking_b_z_all"], batch_size=2000)

def update_rankings_b_z_u(olympiad_id, zone_id):
    """Updates rankings_b_z_u for zone - unofficial only."""
    scores = list(ScoreSheet.objects.filter(
        olympiad_id=olympiad_id,
        user__data__province__zone_id=zone_id,
        is_official=False
    ).order_by("total"))

    if not scores:
        return

    count = len(scores)
    lowest_rank = 1
    prev_score = None
    score_count = 0

    for sheet in scores:
        if sheet.total != prev_score:
            lowest_rank += score_count
            score_count = 1
        else:
            score_count += 1

        sheet.ranking_b_z_u = count - lowest_rank + 1
        prev_score = sheet.total

    ScoreSheet.objects.bulk_update(scores, ["ranking_b_z_u"], batch_size=2000)

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
