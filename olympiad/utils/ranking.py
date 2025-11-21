from ..models import Olympiad, Result, ScoreSheet


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
        scores = list(ScoreSheet.objects.filter(olympiad=olympiad,user__data__province_id=province_id,is_official=True).order_by("-total"))

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
        scores = list(ScoreSheet.objects.filter(olympiad=olympiad,user__data__province__zone_id=zone_id,is_official=True).order_by("-total"))

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
        scores = list(ScoreSheet.objects.filter(olympiad=olympiad,user__data__province_id=province_id,is_official=True).order_by("total"))
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
        scores = list(ScoreSheet.objects.filter(olympiad=olympiad,user__data__province__zone_id=zone_id,is_official=True).order_by("total"))
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
