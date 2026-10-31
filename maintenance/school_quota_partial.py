"""first_to_second_by_school_quota-ийн сонголтыг зөвхөн заасан (сургууль, I давааны олимпиад)
хосуудад дахин хийнэ. Бусад сургуулийн Award/prizes/группт хүрэхгүй.
Ашиглах (repo root-оос):
  PAIRS="[(416,280),(585,279)]" python manage.py shell < maintenance/school_quota_partial.py          # dry-run
  APPLY=1 PAIRS="[(416,280)]" python manage.py shell < maintenance/school_quota_partial.py         # хадгалах
Өмнө нь calculate_scores + generate_scoresheets ажиллуулсан байх ёстой; дараа нь олимпиадын cache-г цэвэрлэнэ.
"""
import os
from django.db import transaction
from olympiad.models import Award, Olympiad, ScoreSheet
from schools.models import School
from olympiad.utils.round2_quota import compute_school_quota_table
from olympiad.utils.group_management import ensure_olympiad_has_group
from olympiad.management.commands.first_to_second_by_school_quota import (
    select_school_students, append_place, strip_our_places, PLACE_SCHOOL, OUR_PLACES,
)

APPLY = os.environ.get('APPLY') == '1'
PAIRS = eval(os.environ['PAIRS'])

with transaction.atomic():
    for school_id, oid in PAIRS:
        school = School.objects.get(id=school_id)
        round2 = Olympiad.objects.get(id=oid).next_round
        r1_ids = list(Olympiad.objects.filter(next_round=round2).values_list('id', flat=True))
        table = compute_school_quota_table(school.province, round2)
        row = next(d for d in table['schools_data'] if d['school'] and d['school'].id == school_id)
        quota = row['total_quota']

        best = {}
        for s in ScoreSheet.objects.filter(olympiad_id__in=r1_ids, school_id=school_id,
                                           is_official=True, total__gt=0).select_related('user'):
            if s.user_id not in best or (s.total or 0) > (best[s.user_id].total or 0):
                best[s.user_id] = s
        rows = [{'user_id': uid, 'total': s.total or 0, 'last_name': s.user.last_name,
                 'first_name': s.user.first_name, 'scoresheet': s} for uid, s in best.items()]
        picked = {r['user_id']: r for r in select_school_students(rows, quota, 'fewer')}

        school_users = set(ScoreSheet.objects.filter(olympiad_id__in=r1_ids, school_id=school_id)
                           .values_list('user_id', flat=True))
        current = set(Award.objects.filter(olympiad_id__in=r1_ids, place__in=OUR_PLACES,
                                           contestant_id__in=school_users)
                      .values_list('contestant_id', flat=True))
        add, remove = set(picked) - current, current - set(picked)
        print(f'{school.name} ({school_id}) | {round2.name} | квот {quota} | сонгогдсон {len(picked)} '
              f'| өмнө {len(current)} | +{sorted(add)} -{sorted(remove)}')
        for uid in sorted(add | remove):
            s = best.get(uid)
            print(f'   {"+" if uid in add else "-"} {uid} {s.user.get_full_name() if s else ""} оноо {s.total if s else "—"}')

        group, _ = ensure_olympiad_has_group(round2)
        for uid in remove:
            Award.objects.filter(olympiad_id__in=r1_ids, contestant_id=uid, place__in=OUR_PLACES).delete()
            for s in ScoreSheet.objects.filter(olympiad_id__in=r1_ids, user_id=uid):
                s.prizes = strip_our_places(s.prizes); s.save(update_fields=['prizes'])
            group.user_set.remove(uid)
        for uid in add:
            s = picked[uid]['scoresheet']
            Award.objects.create(olympiad_id=s.olympiad_id, contestant_id=uid, place=PLACE_SCHOOL)
            s.prizes = append_place(s.prizes, PLACE_SCHOOL); s.save(update_fields=['prizes'])
            group.user_set.add(uid)

    if not APPLY:
        print('DRY RUN — rollback'); transaction.set_rollback(True)
