# olympiad/management/commands/second_to_third_fourth_by_ranking.py

from django.core.management.base import BaseCommand, CommandError
from olympiad.models import ScoreSheet, Olympiad, Award
from olympiad.utils.group_management import ensure_olympiad_has_group
from django.contrib.auth.models import User, Group
import pandas as pd
import numpy as np
from datetime import datetime
import os


class Logger:
    """Дэлгэц болон файлд зэрэг бичих logger"""

    def __init__(self, log_file_path, stdout):
        self.log_file_path = log_file_path
        self.stdout = stdout
        self.log_lines = []

    def write(self, message, style_func=None):
        """Дэлгэцэнд болон log-д бичих"""
        self.log_lines.append(message)
        if style_func:
            self.stdout.write(style_func(message))
        else:
            self.stdout.write(message)

    def save(self):
        """Log файлыг хадгалах"""
        with open(self.log_file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.log_lines))


def read_config_file(file_path):
    """
    2-р давааны тохиргооны файл уншиж, олимпиадын ID-ууд болон босго оноог буцаана.

    Файлын бүтэц:
    Мэдээлэл хэсэг:
        Ангилал | second round ID | third round ID | fourth round ID
        C       | 199            |                |
        D       | 200            | 207            |
        E       | 201            | 208            | 218
        ...

    Аймгууд хэсэг:
        ID | Нэр | C | D | E | F | S | T
        1  | ... | 0 | 10 | 10 | 10 | 5 | 5
        ...

    Returns:
        category_config: dict {category: {'second': id, 'third': id, 'fourth': id}}
        quota_df: DataFrame with columns ['region_id', category1, category2, ...]
    """
    df_raw = pd.read_excel(file_path, header=None)

    category_config = {}
    quota_df = None

    # Мэдээлэл болон аймгууд хэсгийн эхлэлийг олох
    info_start_idx = None
    aimag_start_idx = None

    for idx, row in df_raw.iterrows():
        first_cell = str(row[0]).strip().lower() if pd.notna(row[0]) else ''

        if 'мэдээлэл' in first_cell or 'ангилал' in first_cell:
            info_start_idx = idx

        if 'аймаг' in first_cell or (pd.notna(row[0]) and str(row[0]).strip().upper() == 'ID' and idx > 3):
            aimag_start_idx = idx
            break

    # Мэдээлэл хэсгээс олимпиадын ID-уудыг унших
    if info_start_idx is not None and aimag_start_idx is not None:
        # Header мөр (second round ID, third round ID, fourth round ID)
        header_row = df_raw.iloc[info_start_idx + 1] if info_start_idx + 1 < len(df_raw) else None

        for idx in range(info_start_idx + 2, aimag_start_idx):
            row = df_raw.iloc[idx]
            if pd.notna(row[0]):
                category = str(row[0]).strip()
                # Хоосон мөр эсвэл "Аймгууд" гэх мэт толгой үгийг алгасах
                if category and category.lower() not in ['', 'аймгууд', 'аймаг', 'дүүрэг']:
                    category_config[category] = {
                        'second': int(float(row[1])) if pd.notna(row[1]) and str(row[1]).replace('.', '').isdigit() else None,
                        'third': int(float(row[2])) if pd.notna(row[2]) and str(row[2]).replace('.', '').isdigit() else None,
                        'fourth': int(float(row[3])) if len(row) > 3 and pd.notna(row[3]) and str(row[3]).replace('.', '').isdigit() else None,
                    }

    # Аймгууд хэсгээс босго оноог унших
    if aimag_start_idx is not None:
        quota_df = pd.read_excel(file_path, header=aimag_start_idx, skiprows=0)

        if 'ID' in quota_df.columns:
            quota_df = quota_df.rename(columns={'ID': 'region_id'})

        cols_to_keep = ['region_id'] + [col for col in quota_df.columns if col not in ['region_id', 'Нэр']]
        quota_df = quota_df[cols_to_keep]

        quota_df = quota_df.dropna(subset=['region_id'])

    return category_config, quota_df


def select_for_third_round(df, quota_config):
    """
    2-р давааны үр дүнгээс 3-р даваанд шалгарах сурагчдыг сонгоно.
    Байрын дугаараар (ranking_a_p) квот олгоно.

    df: columns = ['name', 'school', 'school_id', 'region', 'region_id', 'category',
                   'score', 'ranking_a_p', 'scoresheet_id', 'user_id', 'olympiad_id']
    quota_config: DataFrame with region_id and category columns containing quota (number of students)

    Returns: DataFrame with selection_type column
    """
    # 0 оноотой оролцогчдыг хасна
    df = df[df['score'] > 0].copy()

    result = []

    # Аймаг/дүүрэг бүрээр ажиллах
    for region_id in df['region_id'].unique():
        region_df = df[df['region_id'] == region_id]

        # Тухайн аймгийн квотыг авах
        region_quota = quota_config[quota_config['region_id'] == region_id]

        if region_quota.empty:
            continue

        # Ангилал бүрээр шалгах
        for category in df['category'].unique():
            if category not in quota_config.columns:
                continue

            quota = region_quota[category].values[0] if not region_quota.empty else 0

            if pd.isna(quota) or quota <= 0:
                continue

            quota = int(quota)

            # Тухайн аймаг, ангиллын сурагчдыг сонгох
            category_df = region_df[region_df['category'] == category].copy()

            if len(category_df) == 0:
                continue

            # Байрын дугаараар эрэмбэлэх (ranking_a_p бага = өндөр байр)
            ordered = category_df.sort_values(
                by=['ranking_a_p', 'score'],
                ascending=[True, False]
            )

            if len(ordered) <= quota:
                # Бүх сурагчийг авна
                selected = ordered.copy()
            else:
                # quota дахь сурагчийн оноог авах
                cutoff_score = ordered.iloc[quota - 1]['score']
                # Дараагийн сурагчийн оноо
                next_score = ordered.iloc[quota]['score']

                if cutoff_score == next_score:
                    # Ижил оноотой бол тэр оноотой бүгдийг хасна (квотоос хэтрэхгүй байх)
                    selected = ordered[ordered['score'] > cutoff_score].copy()
                else:
                    # Ялгаатай бол эхний quota-г авна
                    selected = ordered.head(quota).copy()

            if len(selected) > 0:
                selected['selection_type'] = '2.2 эрх'
                result.append(selected)

    if not result:
        return pd.DataFrame()

    return pd.concat(result).reset_index(drop=True)


def select_for_fourth_round(df, quota_config, max_per_province=2):
    """
    2-р давааны үр дүнгээс 4-р даваанд шалгарах сурагчдыг сонгоно.
    Байрын дугаараар (ranking_a_p) квот олгоно.
    Аймаг бүрээс max_per_province-оос хэтрэхгүй сурагч орно.
    Оноо тэнцсэн тохиолдолд квотоос хэтрэхгүйгээр тэнцүү оноотой сурагчдыг хасна.

    df: columns = ['name', 'school', 'school_id', 'region', 'region_id', 'category',
                   'score', 'ranking_a_p', 'scoresheet_id', 'user_id', 'olympiad_id']
    quota_config: DataFrame with region_id and category columns containing quota (number of students)
    max_per_province: Аймаг бүрээс орох хамгийн их сурагчийн тоо (default: 2)

    Returns: DataFrame with selection_type column
    """
    # 0 оноотой оролцогчдыг хасна
    df = df[df['score'] > 0].copy()

    result = []

    # Аймаг/дүүрэг бүрээр ажиллах
    for region_id in df['region_id'].unique():
        region_df = df[df['region_id'] == region_id]

        # Тухайн аймгийн квотыг авах
        region_quota = quota_config[quota_config['region_id'] == region_id]

        if region_quota.empty:
            continue

        # Ангилал бүрээр шалгах
        for category in df['category'].unique():
            if category not in quota_config.columns:
                continue

            quota = region_quota[category].values[0] if not region_quota.empty else 0

            if pd.isna(quota) or quota <= 0:
                continue

            # 4-р давааны хувьд max_per_province-оос хэтрэхгүй
            quota = min(int(quota), max_per_province)

            # Тухайн аймаг, ангиллын сурагчдыг сонгох
            category_df = region_df[region_df['category'] == category].copy()

            if len(category_df) == 0:
                continue

            # Байрын дугаараар эрэмбэлэх (ranking_a_p бага = өндөр байр)
            ordered = category_df.sort_values(
                by=['ranking_a_p', 'score'],
                ascending=[True, False]
            )

            if len(ordered) <= quota:
                # Бүх сурагчийг авна
                selected = ordered.copy()
            else:
                # quota дахь сурагчийн оноог авах
                cutoff_score = ordered.iloc[quota - 1]['score']
                # Дараагийн сурагчийн оноо
                next_score = ordered.iloc[quota]['score']

                if cutoff_score == next_score:
                    # Ижил оноотой бол тэр оноотой бүгдийг хасна (квотоос хэтрэхгүй байх)
                    selected = ordered[ordered['score'] > cutoff_score].copy()
                else:
                    # Ялгаатай бол эхний quota-г авна
                    selected = ordered.head(quota).copy()

            if len(selected) > 0:
                selected['selection_type'] = 'Улсын эрх'
                result.append(selected)

    if not result:
        return pd.DataFrame()

    return pd.concat(result).reset_index(drop=True)


def add_students_to_olympiad_group(olympiad_id, student_user_ids, stdout, round_name=""):
    """
    Сурагчдыг олимпиадын группт нэмнэ. Групп байхгүй бол үүсгэнэ.

    Args:
        olympiad_id: Олимпиадын ID
        student_user_ids: Сурагчдын user_id-ийн жагсаалт
        stdout: Command stdout for logging
        round_name: Давааны нэр (логд харуулах)

    Returns:
        dict with statistics
    """
    stats = {
        'group_created': False,
        'students_added': 0,
        'students_already_in_group': 0,
    }

    if not olympiad_id or not student_user_ids:
        return stats

    try:
        olympiad = Olympiad.objects.get(id=olympiad_id)
    except Olympiad.DoesNotExist:
        stdout.write(f'  ⚠ {round_name} олимпиад ID={olympiad_id} олдсонгүй')
        return stats

    # Олимпиадад групп байгаа эсэхийг шалгаад, байхгүй бол үүсгэх
    group, created = ensure_olympiad_has_group(
        olympiad,
        group_name_template=f"Round_{olympiad.round}_{olympiad.id}_{{olympiad.id}}"
    )

    if created:
        stats['group_created'] = True
        stdout.write(f'  ✓ {round_name} групп үүслээ: {group.name}')
    else:
        stdout.write(f'  ↻ {round_name} групп ашигласан: {group.name}')

    # Сурагчдыг группт нэмэх
    for user_id in student_user_ids:
        try:
            user = User.objects.get(id=user_id)
            if not group.user_set.filter(id=user_id).exists():
                group.user_set.add(user)
                stats['students_added'] += 1
            else:
                stats['students_already_in_group'] += 1
        except User.DoesNotExist:
            pass

    stdout.write(
        f'    → {stats["students_added"]} шинээр нэмэгдсэн, '
        f'{stats["students_already_in_group"]} аль хэдийн байсан | '
        f'Олимпиад: {olympiad.name} (ID={olympiad.id})'
    )

    return stats


class Command(BaseCommand):
    help = '''2-р давааны үр дүнгээс 3-р болон 4-р даваанд шалгарах сурагчдыг сонгоно.

    4-р даваанд аймаг бүрээс 2-оос хэтрэхгүй сурагч орно.
    Оноо тэнцсэн тохиолдолд квотоос хэтрэхгүйгээр тэнцүү оноотой сурагчдыг хасна.

    Жишээ:
      # Dry-run хийж үр дүнг харах
      python manage.py second_to_third_fourth_by_ranking --config-file second_round_quota.xlsx --dry-run

      # Өгөгдөл хадгалах
      python manage.py second_to_third_fourth_by_ranking --config-file second_round_quota.xlsx

    Дэлгэрэнгүй: ADDITIONAL_QUOTA_GUIDE.md, QUICK_START.md
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            '--config-file',
            type=str,
            required=True,
            help='Тохиргооны Excel файлын зам (олимпиадын ID + квот)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Өгөгдөл хадгалахгүй, зөвхөн үр дүнг харуулна.',
        )
        parser.add_argument(
            '--max-fourth-per-province',
            type=int,
            default=2,
            help='4-р даваанд аймаг бүрээс орох хамгийн их сурагчийн тоо (default: 2)',
        )
        parser.add_argument(
            '--log-file',
            type=str,
            default=None,
            help='Log файлын нэр (default: second_to_third_fourth_YYYYMMDD_HHMMSS.log)',
        )

    def handle(self, *args, **options):
        config_file = options['config_file']
        dry_run = options['dry_run']
        max_fourth_per_province = options['max_fourth_per_province']

        # Log файлын нэр
        log_file = options['log_file']
        if not log_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = f'second_to_third_fourth_{timestamp}.log'

        # Logger үүсгэх
        log = Logger(log_file, self.stdout)

        log.write(f'=' * 70)
        log.write(f'2-р давааны үр дүнгээс 3-р, 4-р даваанд шалгаруулах')
        log.write(f'Огноо: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        log.write(f'=' * 70)

        # Excel файлаас тохиргоо уншиж авах
        try:
            category_config, quota_config = read_config_file(config_file)
            log.write(f'\n✓ Тохиргоо уншигдлаа: {config_file}', self.style.SUCCESS)
            log.write(f'  Ангилал → Олимпиад тохиргоо:')
            for cat, ids in category_config.items():
                log.write(f'    {cat}: 2-р даваа={ids["second"]}, 3-р даваа={ids["third"]}, 4-р даваа={ids["fourth"]}')
            if quota_config is not None:
                log.write(f'  Квот тохиргоо: {len(quota_config)} аймаг/дүүрэг\n')
        except Exception as e:
            raise CommandError(f'Тохиргооны файл уншихад алдаа: {e}')

        if not category_config:
            raise CommandError('Тохиргооны файлд олимпиадын ID байхгүй байна')

        # Аймгуудын нэрийг авах (quota_config-оос)
        region_names = {}
        if quota_config is not None:
            # Нэрийг Excel-ээс авах
            df_raw = pd.read_excel(config_file, header=None)
            for idx, row in df_raw.iterrows():
                if pd.notna(row[0]) and str(row[0]).replace('.', '').isdigit():
                    region_id = int(float(row[0]))
                    if pd.notna(row[1]):
                        region_names[region_id] = str(row[1])

        # Бүх олимпиадын үр дүнг цуглуулах
        all_third_selected = []
        all_fourth_selected = []

        for category, olympiad_ids in category_config.items():
            second_round_id = olympiad_ids.get('second')
            third_round_id = olympiad_ids.get('third')
            fourth_round_id = olympiad_ids.get('fourth')

            if not second_round_id:
                continue

            log.write(f'\n{"="*60}', self.style.HTTP_INFO)
            log.write(f'Ангилал: {category}', self.style.HTTP_INFO)
            log.write(f'{"="*60}\n', self.style.HTTP_INFO)

            try:
                second_olympiad = Olympiad.objects.get(id=second_round_id)
            except Olympiad.DoesNotExist:
                log.write(f'⚠ 2-р давааны олимпиад ID={second_round_id} олдсонгүй. Алгасав.\n', self.style.WARNING)
                continue

            log.write(f'2-р давааны олимпиад: {second_olympiad.name} (ID={second_round_id})')
            if third_round_id:
                log.write(f'3-р давааны олимпиад ID: {third_round_id}')
            if fourth_round_id:
                log.write(f'4-р давааны олимпиад ID: {fourth_round_id}')

            # ScoreSheet өгөгдөл татах
            scoresheets = ScoreSheet.objects.filter(
                olympiad_id=second_round_id,
                is_official=True
            ).select_related(
                'user__data__province',
                'school'
            )

            if not scoresheets.exists():
                log.write(f'⚠ Онооны хуудас олдсонгүй. Алгасав.\n', self.style.WARNING)
                continue

            # DataFrame үүсгэх
            data = []
            for ss in scoresheets:
                if not ss.user or not hasattr(ss.user, 'data'):
                    continue

                user_data = ss.user.data
                province = user_data.province

                if not province:
                    continue

                data.append({
                    'scoresheet_id': ss.id,
                    'name': f"{ss.user.last_name} {ss.user.first_name}",
                    'user_id': ss.user.id,
                    'school': ss.school.name if ss.school else 'Тодорхойгүй',
                    'school_id': ss.school.id if ss.school else None,
                    'region': province.name,
                    'region_id': province.id,
                    'category': category,
                    'second_olympiad_id': second_round_id,
                    'third_olympiad_id': third_round_id,
                    'fourth_olympiad_id': fourth_round_id,
                    'score': ss.total or 0,
                    'ranking_a_p': ss.ranking_a_p or 99999,
                })

            if not data:
                log.write(f'⚠ Боловсруулах өгөгдөл олдсонгүй. Алгасав.\n', self.style.WARNING)
                continue

            df = pd.DataFrame(data)
            log.write(f'Нийт оролцогч: {len(df)}')

            # 3-р даваанд сонгох
            if third_round_id and quota_config is not None:
                selected_third = select_for_third_round(df, quota_config)
                if not selected_third.empty:
                    all_third_selected.append(selected_third)
                    log.write(f'  3-р даваанд сонгогдсон: {len(selected_third)}')
                else:
                    log.write(f'  3-р даваанд сонгогдсон: 0')

            # 4-р даваанд сонгох (аймаг бүрээс max_fourth_per_province)
            if fourth_round_id and quota_config is not None:
                selected_fourth = select_for_fourth_round(df, quota_config, max_fourth_per_province)
                if not selected_fourth.empty:
                    all_fourth_selected.append(selected_fourth)
                    log.write(f'  4-р даваанд сонгогдсон: {len(selected_fourth)}')
                else:
                    log.write(f'  4-р даваанд сонгогдсон: 0')

        # === Нийт үр дүн ===
        log.write(f'\n{"="*60}', self.style.HTTP_INFO)
        log.write('НИЙТ ҮР ДҮН', self.style.HTTP_INFO)
        log.write(f'{"="*60}\n', self.style.HTTP_INFO)

        # 3-р даваа
        combined_third = pd.concat(all_third_selected, ignore_index=True) if all_third_selected else pd.DataFrame()
        # 4-р даваа
        combined_fourth = pd.concat(all_fourth_selected, ignore_index=True) if all_fourth_selected else pd.DataFrame()

        log.write(f'3-р даваанд нийт сонгогдсон: {len(combined_third)}', self.style.SUCCESS)
        log.write(f'4-р даваанд нийт сонгогдсон: {len(combined_fourth)}', self.style.SUCCESS)

        # Статистик
        if not combined_third.empty:
            log.write('\n--- 3-р даваа: Ангиллаар ---')
            cat_stats = combined_third.groupby('category').size()
            for cat, count in cat_stats.items():
                log.write(f'  {cat}: {count}')

            log.write('\n--- 3-р даваа: Аймаг/дүүргээр (топ 10) ---')
            region_stats = combined_third.groupby('region').size().sort_values(ascending=False).head(10)
            for region, count in region_stats.items():
                log.write(f'  {region}: {count}')

        if not combined_fourth.empty:
            log.write('\n--- 4-р даваа: Ангиллаар ---')
            cat_stats = combined_fourth.groupby('category').size()
            for cat, count in cat_stats.items():
                log.write(f'  {cat}: {count}')

            log.write('\n--- 4-р даваа: Аймаг/дүүргээр ---')
            region_stats = combined_fourth.groupby('region').size().sort_values(ascending=False)
            for region, count in region_stats.items():
                log.write(f'  {region}: {count}')

        # === КВОТ VS АВСАН ЭРХ (Дэлгэрэнгүй) ===
        log.write(f'\n{"="*70}')
        log.write('АЙМАГ БҮРИЙН КВОТ VS АВСАН ЭРХ (3-р даваа)')
        log.write(f'{"="*70}')

        if quota_config is not None and not combined_third.empty:
            # Ангилал бүрээр
            categories_with_third = [cat for cat, ids in category_config.items() if ids.get('third')]

            for category in categories_with_third:
                if category not in quota_config.columns:
                    continue

                log.write(f'\n--- Ангилал: {category} ---')
                log.write(f'{"Аймаг/Дүүрэг":<35} {"Квот":>6} {"Авсан":>6} {"Зөрүү":>6}')
                log.write('-' * 55)

                total_quota = 0
                total_selected = 0

                for idx, row in quota_config.iterrows():
                    region_id = int(row['region_id'])
                    quota = int(row[category]) if pd.notna(row[category]) else 0
                    region_name = region_names.get(region_id, f'ID={region_id}')

                    # Энэ аймаг, ангиллаас хэдэн сурагч сонгогдсон
                    selected_count = len(combined_third[
                        (combined_third['region_id'] == region_id) &
                        (combined_third['category'] == category)
                    ])

                    diff = selected_count - quota
                    diff_str = f'+{diff}' if diff > 0 else str(diff)

                    if quota > 0 or selected_count > 0:
                        log.write(f'{region_name:<35} {quota:>6} {selected_count:>6} {diff_str:>6}')
                        total_quota += quota
                        total_selected += selected_count

                log.write('-' * 55)
                log.write(f'{"НИЙТ":<35} {total_quota:>6} {total_selected:>6} {total_selected - total_quota:>6}')

        # === 4-р давааны квот vs авсан эрх ===
        log.write(f'\n{"="*70}')
        log.write(f'АЙМАГ БҮРИЙН КВОТ VS АВСАН ЭРХ (4-р даваа, max {max_fourth_per_province}/аймаг)')
        log.write(f'{"="*70}')

        if quota_config is not None and not combined_fourth.empty:
            categories_with_fourth = [cat for cat, ids in category_config.items() if ids.get('fourth')]

            for category in categories_with_fourth:
                if category not in quota_config.columns:
                    continue

                log.write(f'\n--- Ангилал: {category} ---')
                log.write(f'{"Аймаг/Дүүрэг":<35} {"Квот":>6} {"Max":>4} {"Авсан":>6} {"Зөрүү":>6}')
                log.write('-' * 60)

                total_quota = 0
                total_selected = 0

                for idx, row in quota_config.iterrows():
                    region_id = int(row['region_id'])
                    quota = int(row[category]) if pd.notna(row[category]) else 0
                    effective_quota = min(quota, max_fourth_per_province)
                    region_name = region_names.get(region_id, f'ID={region_id}')

                    selected_count = len(combined_fourth[
                        (combined_fourth['region_id'] == region_id) &
                        (combined_fourth['category'] == category)
                    ])

                    diff = selected_count - effective_quota
                    diff_str = f'+{diff}' if diff > 0 else str(diff)

                    if quota > 0 or selected_count > 0:
                        log.write(f'{region_name:<35} {quota:>6} {max_fourth_per_province:>4} {selected_count:>6} {diff_str:>6}')
                        total_quota += effective_quota
                        total_selected += selected_count

                log.write('-' * 60)
                log.write(f'{"НИЙТ":<35} {total_quota:>6} {"":>4} {total_selected:>6} {total_selected - total_quota:>6}')

        if dry_run:
            log.write(self.style.WARNING('\n--dry-run: Өгөгдөл хадгалагдаагүй.'))

            if not combined_third.empty:
                log.write('\n--- 3-р даваанд сонгогдсон сурагчид (эхний 30) ---')
                log.write(f'{"Ангилал":<4} {"Нэр":<30} {"Аймаг":<25} {"Оноо":>6} {"Байр":>5}')
                log.write('-' * 75)
                for idx, row in combined_third.head(30).iterrows():
                    log.write(f"{row['category']:<4} {row['name']:<30} {row['region']:<25} {row['score']:>6} {int(row['ranking_a_p']):>5}")

            if not combined_fourth.empty:
                log.write('\n--- 4-р даваанд сонгогдсон сурагчид (эхний 30) ---')
                log.write(f'{"Ангилал":<4} {"Нэр":<30} {"Аймаг":<25} {"Оноо":>6} {"Байр":>5}')
                log.write('-' * 75)
                for idx, row in combined_fourth.head(30).iterrows():
                    log.write(f"{row['category']:<4} {row['name']:<30} {row['region']:<25} {row['score']:>6} {int(row['ranking_a_p']):>5}")
        else:
            # === Өгөгдөл хадгалах ===
            log.write('\nӨгөгдөл хадгалж байна...', self.style.HTTP_INFO)

            # 3-р давааны Award үүсгэх
            if not combined_third.empty:
                # Хуучин award-уудыг устгах
                second_olympiad_ids_for_third = combined_third['second_olympiad_id'].dropna().unique().tolist()

                # Хуучин болон шинэ нэртэй award-уудыг устгах
                deleted_count, _ = Award.objects.filter(
                    olympiad_id__in=second_olympiad_ids_for_third,
                    place__in=['2.2 эрх', '3-р даваанд шалгарсан']
                ).delete()
                if deleted_count:
                    log.write(f'Хуучин {deleted_count} 3-р давааны award устгагдлаа.')

                # Шинээр үүсгэх
                created_third = 0
                for idx, row in combined_third.iterrows():
                    Award.objects.create(
                        olympiad_id=row['second_olympiad_id'],
                        contestant_id=row['user_id'],
                        place=row['selection_type']
                    )
                    created_third += 1
                log.write(f'{created_third} 3-р давааны award үүсгэгдлээ.', self.style.SUCCESS)

            # 4-р давааны Award үүсгэх
            if not combined_fourth.empty:
                # Хуучин award-уудыг устгах
                second_olympiad_ids_for_fourth = combined_fourth['second_olympiad_id'].dropna().unique().tolist()

                # Хуучин болон шинэ нэртэй award-уудыг устгах
                deleted_count, _ = Award.objects.filter(
                    olympiad_id__in=second_olympiad_ids_for_fourth,
                    place__in=['Улсын эрх', '4-р даваанд шалгарсан']
                ).delete()
                if deleted_count:
                    log.write(f'Хуучин {deleted_count} 4-р давааны award устгагдлаа.')

                # Шинээр үүсгэх
                created_fourth = 0
                for idx, row in combined_fourth.iterrows():
                    Award.objects.create(
                        olympiad_id=row['second_olympiad_id'],
                        contestant_id=row['user_id'],
                        place=row['selection_type']
                    )
                    created_fourth += 1
                log.write(f'{created_fourth} 4-р давааны award үүсгэгдлээ.', self.style.SUCCESS)

            # ScoreSheet prizes талбарыг шинэчлэх
            log.write('ScoreSheet prizes талбарыг шинэчилж байна...')

            # Бүх холбогдох олимпиадын ID-ууд
            all_second_olympiad_ids = list(set(
                combined_third['second_olympiad_id'].dropna().tolist() if not combined_third.empty else []
            ) | set(
                combined_fourth['second_olympiad_id'].dropna().tolist() if not combined_fourth.empty else []
            ))

            # Хуучин тэмдэглэгээг арилгах
            for ss in ScoreSheet.objects.filter(olympiad_id__in=all_second_olympiad_ids):
                if ss.prizes:
                    # 2.2 эрх, Улсын эрх, хуучин 3-р/4-р даваа холбоотой хэсгийг арилгах
                    parts = [p.strip() for p in ss.prizes.split(',')
                             if '2.2 эрх' not in p and 'Улсын эрх' not in p
                             and '3-р даваа' not in p and '4-р даваа' not in p]
                    ss.prizes = ', '.join(parts) if parts else ''
                    ss.save()

            # Шинээр тэмдэглэх (3-р даваа)
            updated_third = 0
            for idx, row in combined_third.iterrows():
                try:
                    ss = ScoreSheet.objects.get(id=row['scoresheet_id'])
                    selection_type = row['selection_type']
                    if ss.prizes:
                        ss.prizes = f"{ss.prizes}, {selection_type}"
                    else:
                        ss.prizes = selection_type
                    ss.save()
                    updated_third += 1
                except ScoreSheet.DoesNotExist:
                    pass

            # Шинээр тэмдэглэх (4-р даваа)
            updated_fourth = 0
            for idx, row in combined_fourth.iterrows():
                try:
                    ss = ScoreSheet.objects.get(id=row['scoresheet_id'])
                    selection_type = row['selection_type']
                    if ss.prizes:
                        # Аль хэдийн байгаа prizes-ийн ард нэмэх
                        if selection_type not in ss.prizes:
                            ss.prizes = f"{ss.prizes}, {selection_type}"
                    else:
                        ss.prizes = selection_type
                    ss.save()
                    updated_fourth += 1
                except ScoreSheet.DoesNotExist:
                    pass

            log.write(f'{updated_third} ScoreSheet 3-р давааны эрхээр шинэчлэгдлээ.', self.style.SUCCESS)
            log.write(f'{updated_fourth} ScoreSheet 4-р давааны эрхээр шинэчлэгдлээ.', self.style.SUCCESS)

            # === Дараагийн давааны олимпиадын группт нэмэх ===
            log.write(f'\n{"="*60}', self.style.HTTP_INFO)
            log.write('ДАРААГИЙН ДАВААНЫ ГРУППҮҮДЭД НЭМЭХ', self.style.HTTP_INFO)
            log.write(f'{"="*60}\n', self.style.HTTP_INFO)

            total_group_stats = {
                'third_groups_created': 0,
                'third_students_added': 0,
                'fourth_groups_created': 0,
                'fourth_students_added': 0,
            }

            # 3-р давааны олимпиадуудын группт нэмэх
            if not combined_third.empty:
                log.write('3-р давааны группүүд:')
                for third_olympiad_id in combined_third['third_olympiad_id'].dropna().unique():
                    third_olympiad_id = int(third_olympiad_id)
                    student_ids = combined_third[
                        combined_third['third_olympiad_id'] == third_olympiad_id
                    ]['user_id'].tolist()

                    stats = add_students_to_olympiad_group(
                        third_olympiad_id,
                        student_ids,
                        self.stdout,
                        "3-р даваа"
                    )
                    if stats['group_created']:
                        total_group_stats['third_groups_created'] += 1
                    total_group_stats['third_students_added'] += stats['students_added']

            # 4-р давааны олимпиадуудын группт нэмэх
            if not combined_fourth.empty:
                log.write('\n4-р давааны группүүд:')
                for fourth_olympiad_id in combined_fourth['fourth_olympiad_id'].dropna().unique():
                    fourth_olympiad_id = int(fourth_olympiad_id)
                    student_ids = combined_fourth[
                        combined_fourth['fourth_olympiad_id'] == fourth_olympiad_id
                    ]['user_id'].tolist()

                    stats = add_students_to_olympiad_group(
                        fourth_olympiad_id,
                        student_ids,
                        self.stdout,
                        "4-р даваа"
                    )
                    if stats['group_created']:
                        total_group_stats['fourth_groups_created'] += 1
                    total_group_stats['fourth_students_added'] += stats['students_added']

            log.write(f'\n✓ 3-р давааны групп үүссэн: {total_group_stats["third_groups_created"]}')
            log.write(f'✓ 3-р давааны группт нэмэгдсэн: {total_group_stats["third_students_added"]}')
            log.write(f'✓ 4-р давааны групп үүссэн: {total_group_stats["fourth_groups_created"]}')
            log.write(f'✓ 4-р давааны группт нэмэгдсэн: {total_group_stats["fourth_students_added"]}')

            log.write('\n✓ Амжилттай дууслаа!', self.style.SUCCESS)

        # Log файлыг хадгалах
        log.save()
        log.write(f'\n📄 Log файл хадгалагдлаа: {log_file}', self.style.SUCCESS)
