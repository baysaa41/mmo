# olympiad/management/commands/third_to_fourth_by_ranking.py
"""
3-р давааны үр дүнгээс 4-р (Улсын) даваанд шалгарах оролцогчдыг сонгоно.

Бүсийн байрлалаар (ranking_a_z) дараах квотоор эрх олгоно:
  - Бүс 1..4: T ангилал ≤ 1, E/F ангилал тус бүр ≤ 2 (бүс тус бүрт)
  - Бүс 5 (Нийслэл): T ангилал ≤ 5, E/F ангилал тус бүр ≤ 20 (бүс тус бүрт)

Өмнө нь round=4 эрх аваагүй хэрэглэгчдэд л эрх нэмнэ.
Оноо тэнцсэн тохиолдолд квотоос хэтрэхгүйгээр тэнцүү оноотой бүгдийг хасна.
"""

from django.core.management.base import BaseCommand, CommandError
from olympiad.models import ScoreSheet, Olympiad, Award
from olympiad.utils.group_management import ensure_olympiad_has_group
from django.contrib.auth.models import User
import pandas as pd
from datetime import datetime


# Дефолт бүс-ангилалын квот
DEFAULT_ZONE_QUOTAS = {
    'zone1_4': {'T': 1, 'E': 2, 'F': 2},   # Бүс 1..4
    'zone5':   {'T': 5, 'E': 20, 'F': 20}, # Бүс 5 (Нийслэл)
}

# Нийслэлийн бүсийн ID
CAPITAL_ZONE_ID = 5


class Logger:
    """Дэлгэц болон файлд зэрэг бичих logger"""

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
    """
    Тохиргооны Excel файл унших.

    Файлын бүтэц:
        Мэдээлэл
        Ангилал | 3-р даваа ID | 4-р даваа ID
        T       | 250          | 260
        E       | 251          | 261

    Returns:
        dict {category: {'third': olympiad_id, 'fourth': olympiad_id}}
    """
    df_raw = pd.read_excel(file_path, header=None)
    category_config = {}

    # Мэдээлэл хэсгийн эхлэлийг олох
    info_start_idx = 0
    for idx, row in df_raw.iterrows():
        first_cell = str(row[0]).strip().lower() if pd.notna(row[0]) else ''
        if 'мэдээлэл' in first_cell or 'ангилал' in first_cell:
            info_start_idx = idx
            break

    # Ангилал мөрүүдийг унших
    for idx in range(info_start_idx + 1, len(df_raw)):
        row = df_raw.iloc[idx]
        if not pd.notna(row[0]):
            continue

        category = str(row[0]).strip()
        if not category or category.lower() in ('ангилал', 'мэдээлэл', ''):
            continue

        def safe_int(val):
            try:
                if pd.notna(val) and str(val).replace('.', '').isdigit():
                    return int(float(val))
            except (ValueError, TypeError):
                pass
            return None

        third_id = safe_int(row[1]) if len(row) > 1 else None
        fourth_id = safe_int(row[2]) if len(row) > 2 else None

        if third_id:
            category_config[category] = {'third': third_id, 'fourth': fourth_id}

    return category_config


def get_zone_quota(zone_id, category, zone_quotas):
    """
    Бүс болон ангилалаар квотыг авна.
    zone_id == CAPITAL_ZONE_ID → zone5 квот, бусад → zone1_4 квот.
    """
    if zone_id == CAPITAL_ZONE_ID:
        return zone_quotas['zone5'].get(category, 0)
    return zone_quotas['zone1_4'].get(category, 0)


def select_for_fourth_round(df, zone_quotas):
    """
    round=3 дүнгээс round=4-т шалгарах оролцогчдыг сонгоно.

    Аргачлал:
      - Бүсийн байрлалаар (ranking_a_z) эрэмбэлнэ
      - Квотын дагуу эхний N-г сонгоно
      - Оноо тэнцсэн тохиолдолд квотоос хэтрэхгүйгээр тэнцүүг хасна

    df columns:
        name, user_id, scoresheet_id, school, school_id,
        zone_id, zone_name, category,
        third_olympiad_id, fourth_olympiad_id,
        score, ranking_a_z

    Returns:
        DataFrame with 'selection_type' column
    """
    df = df[df['score'] > 0].copy()

    result = []

    for zone_id in sorted(df['zone_id'].unique()):
        zone_df = df[df['zone_id'] == zone_id].copy()
        zone_name = zone_df['zone_name'].iloc[0]

        for category in sorted(zone_df['category'].unique()):
            quota = get_zone_quota(zone_id, category, zone_quotas)

            if quota <= 0:
                continue

            cat_df = zone_df[zone_df['category'] == category].copy()
            if cat_df.empty:
                continue

            # Байрлалаар эрэмбэлэх (ranking_a_z бага = өндөр байр)
            ordered = cat_df.sort_values(
                by=['ranking_a_z', 'score'],
                ascending=[True, False]
            )

            if len(ordered) <= quota:
                selected = ordered.copy()
            else:
                cutoff_score = ordered.iloc[quota - 1]['score']
                next_score = ordered.iloc[quota]['score']

                if cutoff_score == next_score:
                    # Ижил оноотой үед тэр оноотойг хасна (квот хэтрэхгүй)
                    selected = ordered[ordered['score'] > cutoff_score].copy()
                else:
                    selected = ordered.head(quota).copy()

            if not selected.empty:
                selected['selection_type'] = 'Улсын эрх'
                result.append(selected)

    return pd.concat(result, ignore_index=True) if result else pd.DataFrame()


def get_existing_round4_user_ids(fourth_olympiad_id):
    """
    round=4 олимпиадад аль хэдийн эрх авсан хэрэглэгчдийн ID цуглуулна.
    Олимпиадын группт аль хэдийн байгаа хэрэглэгчдийг шалгана.
    """
    if not fourth_olympiad_id:
        return set()
    try:
        olympiad = Olympiad.objects.get(id=fourth_olympiad_id)
        if olympiad.group:
            return set(olympiad.group.user_set.values_list('id', flat=True))
    except Olympiad.DoesNotExist:
        pass
    return set()


def add_users_to_olympiad_group(olympiad_id, user_ids, log, label='4-р даваа'):
    """
    Хэрэглэгчдийг олимпиадын группт нэмнэ. Групп байхгүй бол үүсгэнэ.
    """
    stats = {'group_created': False, 'added': 0, 'already_in': 0}

    if not olympiad_id or not user_ids:
        return stats

    try:
        olympiad = Olympiad.objects.get(id=olympiad_id)
    except Olympiad.DoesNotExist:
        log.write(f'  ⚠ {label} олимпиад ID={olympiad_id} олдсонгүй')
        return stats

    group, created = ensure_olympiad_has_group(olympiad)
    stats['group_created'] = created

    if created:
        log.write(f'  ✓ {label} групп үүслээ: {group.name}')
    else:
        log.write(f'  ↻ {label} групп ашигласан: {group.name}')

    for user_id in user_ids:
        try:
            user = User.objects.get(id=user_id)
            if not group.user_set.filter(id=user_id).exists():
                group.user_set.add(user)
                stats['added'] += 1
            else:
                stats['already_in'] += 1
        except User.DoesNotExist:
            pass

    log.write(
        f'    → {stats["added"]} шинээр нэмэгдсэн, '
        f'{stats["already_in"]} аль хэдийн байсан | '
        f'Олимпиад: {olympiad.name} (ID={olympiad.id})'
    )
    return stats


class Command(BaseCommand):
    help = '''3-р давааны үр дүнгээс 4-р (Улсын) даваанд шалгарах оролцогчдыг сонгоно.

    Бүсийн байрлалаар (ranking_a_z) квот олгоно:
      - Бүс 1..4: T ≤ 1, E/F тус бүр ≤ 2 (бүс тус бүрт)
      - Бүс 5 (Нийслэл): T ≤ 5, E/F тус бүр ≤ 20 (бүс тус бүрт)

    Өмнө нь round=4 эрх аваагүй хэрэглэгчдэд л эрх нэмнэ.

    Жишээ:
      # Dry-run хийж үр дүнг харах
      python manage.py third_to_fourth_by_ranking --config-file third_quota.xlsx --dry-run

      # Өгөгдөл хадгалах
      python manage.py third_to_fourth_by_ranking --config-file third_quota.xlsx

      # Квотыг өөрчлөх
      python manage.py third_to_fourth_by_ranking --config-file third_quota.xlsx \\
          --t-quota-zone1-4 2 --e-quota-zone5 30

    Config файлын бүтэц (Excel):
      Мэдээлэл
      Ангилал  | 3-р даваа ID | 4-р даваа ID
      T        | 250          | 260
      E        | 251          | 261
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            '--config-file',
            type=str,
            required=True,
            help='Тохиргооны Excel файлын зам (ангилал → 3-р/4-р давааны олимпиад ID)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Өгөгдөл хадгалахгүй, зөвхөн үр дүнг харуулна.',
        )
        parser.add_argument(
            '--log-file',
            type=str,
            default=None,
            help='Log файлын нэр (default: third_to_fourth_YYYYMMDD_HHMMSS.log)',
        )
        parser.add_argument(
            '--t-quota-zone1-4',
            type=int,
            default=DEFAULT_ZONE_QUOTAS['zone1_4']['T'],
            help=f'Бүс 1..4-т T ангилалын квот (default: {DEFAULT_ZONE_QUOTAS["zone1_4"]["T"]})',
        )
        parser.add_argument(
            '--e-quota-zone1-4',
            type=int,
            default=DEFAULT_ZONE_QUOTAS['zone1_4']['E'],
            help=f'Бүс 1..4-т E ангилалын квот (default: {DEFAULT_ZONE_QUOTAS["zone1_4"]["E"]})',
        )
        parser.add_argument(
            '--f-quota-zone1-4',
            type=int,
            default=DEFAULT_ZONE_QUOTAS['zone1_4']['F'],
            help=f'Бүс 1..4-т F ангилалын квот (default: {DEFAULT_ZONE_QUOTAS["zone1_4"]["F"]})',
        )
        parser.add_argument(
            '--t-quota-zone5',
            type=int,
            default=DEFAULT_ZONE_QUOTAS['zone5']['T'],
            help=f'Бүс 5-т T ангилалын квот (default: {DEFAULT_ZONE_QUOTAS["zone5"]["T"]})',
        )
        parser.add_argument(
            '--e-quota-zone5',
            type=int,
            default=DEFAULT_ZONE_QUOTAS['zone5']['E'],
            help=f'Бүс 5-т E ангилалын квот (default: {DEFAULT_ZONE_QUOTAS["zone5"]["E"]})',
        )
        parser.add_argument(
            '--f-quota-zone5',
            type=int,
            default=DEFAULT_ZONE_QUOTAS['zone5']['F'],
            help=f'Бүс 5-т F ангилалын квот (default: {DEFAULT_ZONE_QUOTAS["zone5"]["F"]})',
        )

    def handle(self, *args, **options):
        config_file = options['config_file']
        dry_run = options['dry_run']

        zone_quotas = {
            'zone1_4': {
                'T': options['t_quota_zone1_4'],
                'E': options['e_quota_zone1_4'],
                'F': options['f_quota_zone1_4'],
            },
            'zone5': {
                'T': options['t_quota_zone5'],
                'E': options['e_quota_zone5'],
                'F': options['f_quota_zone5'],
            },
        }

        # Log файлын нэр
        log_file = options['log_file']
        if not log_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = f'third_to_fourth_{timestamp}.log'

        log = Logger(log_file, self.stdout)

        log.write('=' * 70)
        log.write('3-р давааны үр дүнгээс 4-р даваанд шалгаруулах')
        log.write(f'Огноо: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        log.write(f'Квот — Бүс 1..4: T={zone_quotas["zone1_4"]["T"]}, E={zone_quotas["zone1_4"]["E"]}, F={zone_quotas["zone1_4"]["F"]}')
        log.write(f'Квот — Бүс 5:    T={zone_quotas["zone5"]["T"]}, E={zone_quotas["zone5"]["E"]}, F={zone_quotas["zone5"]["F"]}')
        if dry_run:
            log.write('[DRY-RUN горим идэвхтэй]')
        log.write('=' * 70)

        # Config файл уншина
        try:
            category_config = read_config_file(config_file)
            log.write(f'\n✓ Тохиргоо уншигдлаа: {config_file}', self.style.SUCCESS)
            for cat, ids in category_config.items():
                log.write(f'  {cat}: 3-р даваа={ids["third"]}, 4-р даваа={ids["fourth"]}')
        except Exception as e:
            raise CommandError(f'Тохиргооны файл уншихад алдаа: {e}')

        if not category_config:
            raise CommandError('Тохиргооны файлд олимпиадын ID байхгүй байна')

        all_selected = []

        # Ангилал бүрийг боловсруулах
        for category, olympiad_ids in category_config.items():
            third_round_id = olympiad_ids.get('third')
            fourth_round_id = olympiad_ids.get('fourth')

            if not third_round_id:
                continue

            log.write(f'\n{"="*60}', self.style.HTTP_INFO)
            log.write(f'Ангилал: {category}', self.style.HTTP_INFO)
            log.write(f'  3-р даваа ID: {third_round_id}', self.style.HTTP_INFO)
            log.write(f'  4-р даваа ID: {fourth_round_id}', self.style.HTTP_INFO)
            log.write(f'{"="*60}', self.style.HTTP_INFO)

            # 3-р давааны олимпиадыг татах
            try:
                third_olympiad = Olympiad.objects.get(id=third_round_id)
            except Olympiad.DoesNotExist:
                log.write(
                    f'⚠ 3-р давааны олимпиад ID={third_round_id} олдсонгүй. Алгасав.',
                    self.style.WARNING
                )
                continue

            log.write(f'3-р давааны олимпиад: {third_olympiad.name}')

            # Аль хэдийн round=4 эрх авсан хэрэглэгчдийг авах
            existing_round4_ids = get_existing_round4_user_ids(fourth_round_id)
            if existing_round4_ids:
                log.write(f'Round=4 эрх аль хэдийн авсан: {len(existing_round4_ids)} хэрэглэгч (хасагдана)')

            # ScoreSheet татах
            scoresheets = ScoreSheet.objects.filter(
                olympiad_id=third_round_id,
                is_official=True,
            ).select_related(
                'user__data__province__zone',
                'school',
            )

            if not scoresheets.exists():
                log.write('⚠ Онооны хуудас олдсонгүй. Алгасав.', self.style.WARNING)
                continue

            # DataFrame үүсгэх
            data = []
            skipped_no_zone = 0
            skipped_existing_right = 0

            for ss in scoresheets:
                if not ss.user or not hasattr(ss.user, 'data'):
                    continue

                user_data = ss.user.data
                province = user_data.province

                if not province or not province.zone:
                    skipped_no_zone += 1
                    continue

                # Аль хэдийн round=4 эрх авсан бол алгасах
                if ss.user.id in existing_round4_ids:
                    skipped_existing_right += 1
                    continue

                zone = province.zone
                data.append({
                    'scoresheet_id': ss.id,
                    'name': f"{ss.user.last_name} {ss.user.first_name}",
                    'user_id': ss.user.id,
                    'school': ss.school.name if ss.school else 'Тодорхойгүй',
                    'school_id': ss.school.id if ss.school else None,
                    'zone_id': zone.id,
                    'zone_name': zone.name,
                    'category': category,
                    'third_olympiad_id': third_round_id,
                    'fourth_olympiad_id': fourth_round_id,
                    'score': ss.total or 0,
                    'ranking_a_z': ss.ranking_a_z or 99999,
                })

            if skipped_no_zone:
                log.write(f'  Бүс тодорхойгүй тул алгасав: {skipped_no_zone}')
            if skipped_existing_right:
                log.write(f'  Round=4 эрх аль хэдийн авсан тул алгасав: {skipped_existing_right}')

            if not data:
                log.write('⚠ Боловсруулах өгөгдөл олдсонгүй. Алгасав.', self.style.WARNING)
                continue

            df = pd.DataFrame(data)
            log.write(f'Боловсруулах оролцогч: {len(df)}')

            # Сонгох
            selected = select_for_fourth_round(df, zone_quotas)

            if selected.empty:
                log.write('  Сонгогдсон: 0')
                continue

            log.write(f'  Сонгогдсон нийт: {len(selected)}')

            # Бүсийн статистик
            for zone_id in sorted(selected['zone_id'].unique()):
                zone_sel = selected[selected['zone_id'] == zone_id]
                zone_name = zone_sel['zone_name'].iloc[0]
                for cat in sorted(zone_sel['category'].unique()):
                    cnt = len(zone_sel[zone_sel['category'] == cat])
                    quota = get_zone_quota(zone_id, cat, zone_quotas)
                    log.write(f'    Бүс {zone_id} ({zone_name}), {cat}: {cnt}/{quota}')

            all_selected.append(selected)

        # === Нийт үр дүн ===
        log.write(f'\n{"="*70}', self.style.HTTP_INFO)
        log.write('НИЙТ ҮР ДҮН', self.style.HTTP_INFO)
        log.write(f'{"="*70}\n', self.style.HTTP_INFO)

        combined = (
            pd.concat(all_selected, ignore_index=True) if all_selected else pd.DataFrame()
        )

        log.write(
            f'4-р даваанд нийт сонгогдсон: {len(combined)}',
            self.style.SUCCESS
        )

        if not combined.empty:
            log.write('\n--- Ангиллаар ---')
            for cat, cnt in combined.groupby('category').size().items():
                log.write(f'  {cat}: {cnt}')

            log.write('\n--- Бүсээр ---')
            for zone, cnt in combined.groupby('zone_name').size().sort_values(ascending=False).items():
                log.write(f'  {zone}: {cnt}')

        # === Dry-run: жагсаалт харуулах ===
        if dry_run:
            log.write(self.style.WARNING('\n--dry-run: Өгөгдөл хадгалагдаагүй.'))

            if not combined.empty:
                log.write('\n--- Сонгогдсон оролцогчид (эхний 50) ---')
                log.write(
                    f'{"Ангилал":<8} {"Нэр":<30} {"Бүс":<20} {"Оноо":>6} {"Байр":>6}'
                )
                log.write('-' * 75)
                for _, row in combined.head(50).iterrows():
                    log.write(
                        f"{row['category']:<8} {row['name']:<30} {row['zone_name']:<20} "
                        f"{row['score']:>6} {int(row['ranking_a_z']):>6}"
                    )
        else:
            # === Өгөгдөл хадгалах ===
            log.write('\nӨгөгдөл хадгалж байна...', self.style.HTTP_INFO)

            if combined.empty:
                log.write('Хадгалах өгөгдөл байхгүй.')
            else:
                third_olympiad_ids = combined['third_olympiad_id'].dropna().unique().tolist()

                # Хуучин award-уудыг устгах
                deleted_count, _ = Award.objects.filter(
                    olympiad_id__in=third_olympiad_ids,
                    place='Улсын эрх',
                ).delete()
                if deleted_count:
                    log.write(f'Хуучин {deleted_count} "Улсын эрх" award устгагдлаа.')

                # Шинэ Award үүсгэх
                created_count = 0
                for _, row in combined.iterrows():
                    Award.objects.create(
                        olympiad_id=row['third_olympiad_id'],
                        contestant_id=row['user_id'],
                        place=row['selection_type'],
                    )
                    created_count += 1
                log.write(f'{created_count} award үүсгэгдлээ.', self.style.SUCCESS)

                # ScoreSheet prizes шинэчлэх
                log.write('ScoreSheet prizes шинэчилж байна...')

                # Хуучин тэмдэглэгээг арилгах
                for ss in ScoreSheet.objects.filter(olympiad_id__in=third_olympiad_ids):
                    if ss.prizes and 'Улсын эрх' in ss.prizes:
                        parts = [
                            p.strip() for p in ss.prizes.split(',')
                            if 'Улсын эрх' not in p
                        ]
                        ss.prizes = ', '.join(parts) if parts else ''
                        ss.save()

                # Шинэ тэмдэглэгээ нэмэх
                updated = 0
                for _, row in combined.iterrows():
                    try:
                        ss = ScoreSheet.objects.get(id=row['scoresheet_id'])
                        label = row['selection_type']
                        if ss.prizes:
                            if label not in ss.prizes:
                                ss.prizes = f"{ss.prizes}, {label}"
                        else:
                            ss.prizes = label
                        ss.save()
                        updated += 1
                    except ScoreSheet.DoesNotExist:
                        pass
                log.write(f'{updated} ScoreSheet шинэчлэгдлээ.', self.style.SUCCESS)

                # 4-р давааны групп
                log.write(f'\n{"="*60}', self.style.HTTP_INFO)
                log.write('4-Р ДАВААНЫ ГРУППҮҮДЭД НЭМЭХ', self.style.HTTP_INFO)
                log.write(f'{"="*60}\n', self.style.HTTP_INFO)

                total_added = 0
                total_created = 0

                for fourth_id in combined['fourth_olympiad_id'].dropna().unique():
                    fourth_id = int(fourth_id)
                    user_ids = (
                        combined[combined['fourth_olympiad_id'] == fourth_id]['user_id']
                        .tolist()
                    )
                    stats = add_users_to_olympiad_group(fourth_id, user_ids, log, '4-р даваа')
                    total_added += stats['added']
                    total_created += int(stats['group_created'])

                log.write(f'\n✓ Группүүд үүслээ: {total_created}')
                log.write(f'✓ Нийт шинээр нэмэгдсэн: {total_added}')

            log.write('\n✓ Амжилттай дууслаа!', self.style.SUCCESS)

        log.save()
        log.write(f'\n📄 Log файл хадгалагдлаа: {log_file}', self.style.SUCCESS)
