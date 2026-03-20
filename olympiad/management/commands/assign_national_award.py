# olympiad/management/commands/assign_national_award.py
"""
Улсын эрх олгох 2 үе шат:

Шат 1 — "Улсын эрх аймаг/дүүрэг" (round=2 ScoreSheet-д):
  Аймаг/дүүрэг бүрт:
    count_A = round=2-д ranking_b_p <= 2 тоо
    Нөхцөл A: round=2 ranking_b_p <= 2
    Нөхцөл B: 2 - count_A > 0 үед round=2-д хилийн байранд тэнцсэн сурагчдаас
              round=3 оноогоор эрэмбэлж (2 - count_A) тоог сонгоно

Шат 2 — Бүсийн эрх (round=3 ScoreSheet-д):
  Шат 1-ийн эрх аваагүй round=3 оролцогчдоос:
    zone 1..4: E, F тус бүр ≤ 2, T ≤ 1  → "Улсын эрх бүсээс"
    zone 5:    E, F тус бүр ≤ 20, T ≤ 5 → "Улсын эрх УБ хотоос"
  Оноо буурах дарааллаар; тэнцвэл тэнцсэн бүгдийг хасна.

Config Excel:
  Ангилал | 2-р даваа ID | 3-р даваа ID | 4-р даваа ID
  C       | 199          | 215          | 230

Жишээ:
  python manage.py assign_national_award --config-file national_award.xlsx --dry-run
  python manage.py assign_national_award --config-file national_award.xlsx
"""

import pandas as pd
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from olympiad.models import ScoreSheet, Olympiad, Award
from olympiad.utils.group_management import ensure_olympiad_has_group

AWARD_PROVINCE = 'Улсын эрх аймаг/дүүрэг'
AWARD_ZONE     = 'Улсын эрх бүсээс'
AWARD_CAPITAL  = 'Улсын эрх УБ хотоос'

MAX_PER_PROVINCE = 2
CAPITAL_ZONE_ID  = 5

ZONE_QUOTAS = {
    'zone1_4': {'T': 1, 'E': 2, 'F': 2},
    'zone5':   {'T': 5, 'E': 20, 'F': 20},
}


class Logger:
    def __init__(self, log_file_path, stdout):
        self.log_file_path = log_file_path
        self.stdout = stdout
        self.log_lines = []

    def write(self, message, style_func=None):
        self.log_lines.append(message)
        if style_func:
            self.stdout.write(style_func(message))
        else:
            self.stdout.write(message)

    def save(self):
        with open(self.log_file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.log_lines))


def read_config_file(file_path):
    df = pd.read_excel(file_path, header=None)
    config = {}

    data_start = 0
    for idx, row in df.iterrows():
        cell = str(row[0]).strip().lower() if pd.notna(row[0]) else ''
        if 'ангилал' in cell or 'мэдээлэл' in cell:
            data_start = idx + 1
            break

    def safe_int(val):
        try:
            if pd.notna(val):
                return int(float(val))
        except (ValueError, TypeError):
            pass
        return None

    for idx in range(data_start, len(df)):
        row = df.iloc[idx]
        if not pd.notna(row[0]):
            continue
        category = str(row[0]).strip()
        if not category:
            continue
        second_id = safe_int(row[1]) if len(row) > 1 else None
        third_id  = safe_int(row[2]) if len(row) > 2 else None
        fourth_id = safe_int(row[3]) if len(row) > 3 else None
        if second_id:
            config[category] = {'second': second_id, 'third': third_id, 'fourth': fourth_id}

    return config


def _select_top(candidates, quota):
    """
    (score, uid, ...) жагсаалтаас оноо буурах дарааллаар quota тоог сонгоно.
    Тэнцвэл тэнцсэн бүгдийг хасна.
    Буцаана: сонгогдсон жагсаалт.
    """
    if not candidates:
        return []
    candidates = sorted(candidates, key=lambda x: x[0], reverse=True)
    if len(candidates) <= quota:
        return candidates
    cutoff = candidates[quota - 1][0]
    nxt    = candidates[quota][0]
    if cutoff == nxt:
        return [c for c in candidates if c[0] > cutoff]
    return candidates[:quota]


# ── ШАТ 1 ──────────────────────────────────────────────────────────────────

def compute_province_awards(second_round_id, third_round_id, log):
    """
    "Улсын эрх аймаг/дүүрэг" авах user_id → info dict буцаана.
    """
    r2_sheets = list(
        ScoreSheet.objects.filter(olympiad_id=second_round_id, is_official=True)
        .select_related('user__data__province')
    )
    if not r2_sheets:
        log.write('  ⚠ round=2 ScoreSheet олдсонгүй.')
        return {}

    r2_by_user = {}
    for ss in r2_sheets:
        if not ss.user or not hasattr(ss.user, 'data') or not ss.user.data.province:
            continue
        r2_by_user[ss.user.id] = {
            'scoresheet_id':  ss.id,
            'province_id':    ss.user.data.province.id,
            'province_name':  ss.user.data.province.name,
            'ranking_b_p':    ss.ranking_b_p or 0,
            'name':           f'{ss.user.last_name} {ss.user.first_name}',
        }

    province_count_a = {}
    for uid, info in r2_by_user.items():
        if 0 < info['ranking_b_p'] <= MAX_PER_PROVINCE:
            pid = info['province_id']
            province_count_a[pid] = province_count_a.get(pid, 0) + 1

    log.write(f'  round=2 нийт оролцогч: {len(r2_by_user)}')

    # Нөхцөл A
    selected = {}
    for uid, info in r2_by_user.items():
        if 0 < info['ranking_b_p'] <= MAX_PER_PROVINCE:
            selected[uid] = {**info, 'condition': 'A'}
    log.write(f'  Нөхцөл A сонгогдсон: {len(selected)}')

    # Нөхцөл B
    if third_round_id:
        r3_score_by_user = {}
        for ss in ScoreSheet.objects.filter(olympiad_id=third_round_id, is_official=True):
            if ss.user:
                r3_score_by_user[ss.user.id] = ss.total or 0

        log.write(f'  round=3 ScoreSheet: {len(r3_score_by_user)}')

        province_non_a = {}
        for uid, info in r2_by_user.items():
            if uid in selected:
                continue
            rbp = info['ranking_b_p']
            if rbp <= 0:
                continue
            province_non_a.setdefault(info['province_id'], []).append((rbp, uid))

        count_b = 0
        for province_id, non_a_list in province_non_a.items():
            remaining = MAX_PER_PROVINCE - province_count_a.get(province_id, 0)
            if remaining <= 0:
                continue

            boundary_rank = min(rbp for rbp, _ in non_a_list)
            boundary_uids = [uid for rbp, uid in non_a_list if rbp == boundary_rank]
            pname = r2_by_user[boundary_uids[0]]['province_name']

            log.write(f'    {pname}: хилийн байр={boundary_rank}, '
                      f'тэнцсэн={len(boundary_uids)}, үлдэх квот={remaining}')

            candidates = [(r3_score_by_user[uid], uid)
                          for uid in boundary_uids if r3_score_by_user.get(uid, 0) > 0]
            if not candidates:
                log.write(f'      → round=3 оролцогч олдсонгүй.')
                continue

            to_select = _select_top(candidates, remaining)
            for score, uid in to_select:
                selected[uid] = {**r2_by_user[uid], 'condition': 'B', 'r3_score': score}
                count_b += 1
            log.write(f'      → {len(to_select)}/{len(candidates)} сонгогдлоо.')

        log.write(f'  Нөхцөл B сонгогдсон: {count_b}')
    else:
        log.write('  round=3 ID байхгүй — нөхцөл B шалгалтгүй.')

    return selected


# ── ШАТ 2 ──────────────────────────────────────────────────────────────────

def compute_zone_awards(third_round_id, category, excluded_user_ids, log):
    """
    round=3-аас excluded_user_ids-д ороогүй оролцогчдод бүсийн квотоор эрх олгоно.
    Буцаана: list of dict (user_id, scoresheet_id, award_place, zone_id, ...)
    """
    r3_sheets = list(
        ScoreSheet.objects.filter(olympiad_id=third_round_id, is_official=True)
        .select_related('user__data__province__zone')
    )
    if not r3_sheets:
        log.write('  ⚠ round=3 ScoreSheet олдсонгүй.')
        return []

    # Бүс бүрт кандидатуудыг цуглуулах
    zone_candidates = {}  # zone_id → [(score, uid, ss, zone_name)]
    for ss in r3_sheets:
        if not ss.user or not hasattr(ss.user, 'data'):
            continue
        if ss.user.id in excluded_user_ids:
            continue
        province = ss.user.data.province
        if not province or not province.zone:
            continue
        score = ss.total or 0
        if score <= 0:
            continue
        zone_id = province.zone.id
        zone_candidates.setdefault(zone_id, []).append(
            (score, ss.user.id, ss, province.zone.name)
        )

    results = []
    for zone_id, candidates in sorted(zone_candidates.items()):
        zone_name  = candidates[0][3]
        is_capital = (zone_id == CAPITAL_ZONE_ID)
        quota_key  = 'zone5' if is_capital else 'zone1_4'
        quota      = ZONE_QUOTAS[quota_key].get(category, 0)
        award_name = AWARD_CAPITAL if is_capital else AWARD_ZONE

        if quota <= 0:
            continue

        log.write(f'    Бүс {zone_id} ({zone_name}), {category}: квот={quota}, '
                  f'нийт кандидат={len(candidates)}')

        to_select = _select_top(candidates, quota)
        for score, uid, ss, _ in to_select:
            results.append({
                'user_id':          uid,
                'scoresheet_id':    ss.id,
                'zone_id':          zone_id,
                'zone_name':        zone_name,
                'award_place':      award_name,
                'score':            score,
                'name':             f'{ss.user.last_name} {ss.user.first_name}',
            })

        log.write(f'      → {len(to_select)} сонгогдлоо ({award_name})')

    return results


# ── БҮЛЭГТ НЭМЭХ ───────────────────────────────────────────────────────────

def add_users_to_olympiad_group(olympiad_id, user_ids, log):
    if not olympiad_id or not user_ids:
        return
    try:
        olympiad = Olympiad.objects.get(id=olympiad_id)
    except Olympiad.DoesNotExist:
        log.write(f'  ⚠ Олимпиад ID={olympiad_id} олдсонгүй.')
        return

    group, created = ensure_olympiad_has_group(olympiad)
    log.write(f'  {"✓ Бүлэг үүслээ" if created else "↻ Бүлэг ашигласан"}: {group.name}')

    added = already_in = 0
    for uid in user_ids:
        try:
            user = User.objects.get(id=uid)
            if not group.user_set.filter(id=uid).exists():
                group.user_set.add(user)
                added += 1
            else:
                already_in += 1
        except User.DoesNotExist:
            pass

    log.write(f'    → {added} шинээр нэмэгдсэн, {already_in} аль хэдийн байсан '
              f'| {olympiad.name} (ID={olympiad_id})')


# ── COMMAND ─────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Улсын эрх олгох: шат 1 аймаг/дүүрэг, шат 2 бүс/нийслэл.'

    def add_arguments(self, parser):
        parser.add_argument('--config-file', type=str, required=True,
            help='Config Excel: Ангилал | 2-р даваа ID | 3-р даваа ID | 4-р даваа ID')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--log-file', type=str, default=None)

    def handle(self, *args, **options):
        config_file = options['config_file']
        dry_run     = options['dry_run']
        log_file    = options['log_file'] or \
                      f'assign_national_award_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

        log = Logger(log_file, self.stdout)
        log.write('=' * 70)
        log.write('Улсын эрх олгох тооцоолол')
        log.write(f'Огноо: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        if dry_run:
            log.write('[DRY-RUN горим]')
        log.write('=' * 70)

        try:
            config = read_config_file(config_file)
        except Exception as e:
            raise CommandError(f'Config файл уншихад алдаа: {e}')
        if not config:
            raise CommandError('Config файлд ангилал олдсонгүй.')

        log.write(f'\n✓ Config: {config_file}')
        for cat, ids in config.items():
            log.write(f'  {cat}: 2={ids["second"]}, 3={ids["third"]}, 4={ids["fourth"]}')

        province_results = []  # шат 1
        zone_results     = []  # шат 2

        for category, ids in config.items():
            second_id = ids['second']
            third_id  = ids['third']
            fourth_id = ids['fourth']

            log.write(f'\n{"="*60}', self.style.HTTP_INFO)
            log.write(f'Ангилал: {category}', self.style.HTTP_INFO)
            log.write(f'{"="*60}', self.style.HTTP_INFO)

            # Олимпиадын нэрийг шалгах
            try:
                log.write(f'  2-р даваа: {Olympiad.objects.get(id=second_id).name} (ID={second_id})')
            except Olympiad.DoesNotExist:
                log.write(f'  ⚠ 2-р даваа ID={second_id} олдсонгүй. Алгасав.', self.style.WARNING)
                continue

            for label, oid, var in [('3-р даваа', third_id, 'third_id'),
                                     ('4-р даваа', fourth_id, 'fourth_id')]:
                if oid:
                    try:
                        log.write(f'  {label}: {Olympiad.objects.get(id=oid).name} (ID={oid})')
                    except Olympiad.DoesNotExist:
                        log.write(f'  ⚠ {label} ID={oid} олдсонгүй.', self.style.WARNING)
                        if var == 'third_id':
                            third_id = None
                        else:
                            fourth_id = None

            # ── Шат 1 ──
            log.write(f'\n  [Шат 1] Аймаг/дүүргийн эрх', self.style.HTTP_INFO)
            selected = compute_province_awards(second_id, third_id, log)
            log.write(f'  Нийт: {len(selected)}', self.style.SUCCESS)

            # Жагсаалт
            log.write(f'  {"Нэр":<30} {"Аймаг":<25} {"Нөхцөл":>6} {"r2_b_p":>7} {"r3_оноо":>8}')
            log.write('  ' + '-' * 76)
            for uid, info in sorted(selected.items(), key=lambda x: x[1]['province_name']):
                log.write(
                    f'  {info["name"]:<30} {info["province_name"]:<25} '
                    f'{info["condition"]:>6} {info["ranking_b_p"]:>7} '
                    f'{str(info.get("r3_score", "-")):>8}'
                )

            for uid, info in selected.items():
                province_results.append({
                    'category':           category,
                    'user_id':            uid,
                    'scoresheet_id':      info['scoresheet_id'],
                    'second_olympiad_id': second_id,
                    'fourth_olympiad_id': fourth_id,
                    'name':               info['name'],
                })

            # ── Шат 2 ──
            if third_id:
                log.write(f'\n  [Шат 2] Бүсийн эрх', self.style.HTTP_INFO)
                excluded = set(selected.keys())
                zone_sel = compute_zone_awards(third_id, category, excluded, log)
                log.write(f'  Нийт бүсийн эрх: {len(zone_sel)}', self.style.SUCCESS)
                for r in zone_sel:
                    zone_results.append({
                        **r,
                        'category':           category,
                        'third_olympiad_id':  third_id,
                        'fourth_olympiad_id': fourth_id,
                    })

        # ── Нийт үр дүн ──
        log.write(f'\n{"="*70}', self.style.HTTP_INFO)
        log.write(f'ШАТ 1 (аймаг/дүүрэг): {len(province_results)}', self.style.SUCCESS)
        log.write(f'ШАТ 2 (бүс):           {len(zone_results)}', self.style.SUCCESS)
        log.write(f'НИЙТ:                  {len(province_results) + len(zone_results)}', self.style.SUCCESS)
        log.write(f'{"="*70}', self.style.HTTP_INFO)

        if dry_run:
            log.write(self.style.WARNING('\n--dry-run: Өгөгдөл хадгалагдаагүй.'))
            log.save()
            log.write(f'\n📄 Log: {log_file}', self.style.SUCCESS)
            return

        log.write('\nӨгөгдөл хадгалж байна...', self.style.HTTP_INFO)

        # ── Шат 1 хадгалах ──
        second_ids = list({r['second_olympiad_id'] for r in province_results})
        if second_ids:
            deleted, _ = Award.objects.filter(
                olympiad_id__in=second_ids, place=AWARD_PROVINCE).delete()
            if deleted:
                log.write(f'Хуучин {deleted} "{AWARD_PROVINCE}" устгагдлаа.')

            created_c = skipped_c = 0
            for r in province_results:
                _, created = Award.objects.get_or_create(
                    olympiad_id=r['second_olympiad_id'],
                    contestant_id=r['user_id'],
                    place=AWARD_PROVINCE,
                )
                if created:
                    created_c += 1
                else:
                    skipped_c += 1
            log.write(f'{created_c} "{AWARD_PROVINCE}" үүсгэгдлээ.', self.style.SUCCESS)
            if skipped_c:
                log.write(f'{skipped_c} давхардал алгасагдлаа.')

            # prizes
            for ss in ScoreSheet.objects.filter(olympiad_id__in=second_ids):
                if ss.prizes and AWARD_PROVINCE in ss.prizes:
                    parts = [p.strip() for p in ss.prizes.split(',') if AWARD_PROVINCE not in p]
                    ss.prizes = ', '.join(parts) if parts else ''
                    ss.save()
            updated = 0
            for r in province_results:
                try:
                    ss = ScoreSheet.objects.get(id=r['scoresheet_id'])
                    if ss.prizes:
                        if AWARD_PROVINCE not in ss.prizes:
                            ss.prizes = f"{ss.prizes}, {AWARD_PROVINCE}"
                    else:
                        ss.prizes = AWARD_PROVINCE
                    ss.save()
                    updated += 1
                except ScoreSheet.DoesNotExist:
                    pass
            log.write(f'{updated} ScoreSheet (шат 1) шинэчлэгдлээ.', self.style.SUCCESS)

        # ── Шат 2 хадгалах ──
        third_ids = list({r['third_olympiad_id'] for r in zone_results})
        if third_ids:
            deleted, _ = Award.objects.filter(
                olympiad_id__in=third_ids,
                place__in=[AWARD_ZONE, AWARD_CAPITAL]).delete()
            if deleted:
                log.write(f'Хуучин {deleted} бүсийн award устгагдлаа.')

            created_c = 0
            for r in zone_results:
                _, created = Award.objects.get_or_create(
                    olympiad_id=r['third_olympiad_id'],
                    contestant_id=r['user_id'],
                    place=r['award_place'],
                )
                if created:
                    created_c += 1
            log.write(f'{created_c} бүсийн award үүсгэгдлээ.', self.style.SUCCESS)

            # prizes
            for ss in ScoreSheet.objects.filter(olympiad_id__in=third_ids):
                if ss.prizes:
                    parts = [p.strip() for p in ss.prizes.split(',')
                             if AWARD_ZONE not in p and AWARD_CAPITAL not in p]
                    ss.prizes = ', '.join(parts) if parts else ''
                    ss.save()
            updated = 0
            for r in zone_results:
                try:
                    ss = ScoreSheet.objects.get(id=r['scoresheet_id'])
                    place = r['award_place']
                    if ss.prizes:
                        if place not in ss.prizes:
                            ss.prizes = f"{ss.prizes}, {place}"
                    else:
                        ss.prizes = place
                    ss.save()
                    updated += 1
                except ScoreSheet.DoesNotExist:
                    pass
            log.write(f'{updated} ScoreSheet (шат 2) шинэчлэгдлээ.', self.style.SUCCESS)

        # ── round=4 бүлэгт нэмэх ──
        log.write(f'\n{"="*60}', self.style.HTTP_INFO)
        log.write('ROUND=4 БҮЛЭГТ НЭМЭХ', self.style.HTTP_INFO)
        log.write(f'{"="*60}', self.style.HTTP_INFO)

        fourth_groups = {}
        for r in province_results + zone_results:
            fid = r.get('fourth_olympiad_id')
            if fid:
                fourth_groups.setdefault(fid, set()).add(r['user_id'])

        if fourth_groups:
            for fourth_id, user_ids in fourth_groups.items():
                add_users_to_olympiad_group(fourth_id, list(user_ids), log)
        else:
            log.write('  4-р давааны ID тохиргоонд байхгүй.')

        log.write('\n✓ Амжилттай дууслаа!', self.style.SUCCESS)
        log.save()
        log.write(f'\n📄 Log: {log_file}', self.style.SUCCESS)
