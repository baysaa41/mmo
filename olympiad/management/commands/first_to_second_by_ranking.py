# olympiad/management/commands/first_to_second_by_ranking.py

from django.core.management.base import BaseCommand, CommandError
from olympiad.models import ScoreSheet, Olympiad, Award
from django.contrib.auth.models import User
import pandas as pd
import numpy as np


def read_quota_config_file(file_path):
    """
    Нэмэлт эрхийн тохиргооны файл уншиж, олимпиадын ID болон босго оноог буцаана.

    Файлын бүтэц:
    Мэдээлэл хэсэг:
        Ангилал | Олимпиадын ID
        C       | 1
        D       | 2
        ...

    Аймгууд хэсэг:
        ID | Нэр | C | D | E | F
        1  | ... | 4 | 3 | ... | ...

    Returns:
        olympiad_ids: dict {category: olympiad_id}
        quota_df: DataFrame with columns ['region_id', category1, category2, ...]
    """
    # Excel файлыг бүтнээр нь header-гүйгээр унших
    df_raw = pd.read_excel(file_path, header=None)

    olympiad_ids = {}
    quota_df = None

    # "Мэдээлэл" эсвэл "Ангилал" гэсэн үгийг хайх (мэдээлэл хэсгийн эхлэл)
    info_start_idx = None
    aimag_start_idx = None

    for idx, row in df_raw.iterrows():
        first_cell = str(row[0]).strip().lower() if pd.notna(row[0]) else ''

        # Мэдээлэл хэсгийн эхлэл
        if 'мэдээлэл' in first_cell or 'ангилал' in first_cell:
            info_start_idx = idx

        # Аймгууд хэсгийн эхлэл
        if 'аймаг' in first_cell or (pd.notna(row[0]) and str(row[0]).strip().upper() == 'ID' and idx > 3):
            aimag_start_idx = idx
            break

    # Мэдээлэл хэсгээс олимпиадын ID-уудыг унших
    if info_start_idx is not None and aimag_start_idx is not None:
        for idx in range(info_start_idx + 1, aimag_start_idx):
            row = df_raw.iloc[idx]
            if pd.notna(row[0]) and pd.notna(row[1]):
                category = str(row[0]).strip()
                olympiad_id = row[1]
                if category and str(olympiad_id).replace('.', '').isdigit():
                    olympiad_ids[category] = int(float(olympiad_id))

    # Аймгууд хэсгээс босго оноог унших
    if aimag_start_idx is not None:
        # Header мөрийг авах (ID, Нэр, C, D, E, F гэх мэт)
        header_row = df_raw.iloc[aimag_start_idx]

        # Өгөгдлийн хэсгийг унших
        quota_df = pd.read_excel(file_path, header=aimag_start_idx, skiprows=0)

        # ID баганыг region_id болгон нэрлэх
        if 'ID' in quota_df.columns:
            quota_df = quota_df.rename(columns={'ID': 'region_id'})

        # Шаардлагагүй багануудыг хасах (Нэр гэх мэт)
        cols_to_keep = ['region_id'] + [col for col in quota_df.columns if col not in ['region_id', 'Нэр']]
        quota_df = quota_df[cols_to_keep]

        # Хоосон мөрүүдийг хасах
        quota_df = quota_df.dropna(subset=['region_id'])

    return olympiad_ids, quota_df


def select_next_stage(df, region_type, additional_quota_config=None):
    """
    df: columns = ['name', 'school', 'school_id', 'region', 'region_id', 'category', 'score', 'ranking_a_p', 'scoresheet_id', 'user_id']
    region_type: 'aimag' or 'duureg'
    additional_quota_config: list of tuples [(region_id, category, threshold_score), ...]
                             Аймаг бүрээр нэмэлт эрх олгох тохиргоо
                             Жишээ: [(15, 'C', 4), (15, 'D', 3)]

    Returns: DataFrame with selection_type column
    """

    # --- Шалгуурын үзүүлэлтүүд (PDF 5.7-р заалт) ---
    if region_type == 'aimag':
        quota_list = 20   # жагсаалтаар
    elif region_type == 'duureg':
        quota_list = 50
    else:
        raise ValueError("region_type must be 'aimag' or 'duureg'")

    # 0 оноотой оролцогчдыг хасна (5.8-р заалт)
    df = df[df['score'] > 0].copy()

    result = []

    # Аймаг/дүүрэг бүрээр ажиллах
    for region, sub in df.groupby('region'):

        # Ангилал бүрийг тусад нь сонгоно
        for category, subcat in sub.groupby('category'):

            # --- 1) Жагсаалтаар эрх олгох (ranking_a_p ашиглана - бага утга = өндөр эрэмбэ) ---
            ordered = subcat.sort_values(
                by=['ranking_a_p', 'name'], ascending=[True, True]
            )

            if len(ordered) <= quota_list:
                # Бүх сурагчийг авна
                selected_list = ordered.copy()
            else:
                # 20/50 дахь сурагчийн оноог авах
                cutoff_score = ordered.iloc[quota_list - 1]['score']

                # Дараагийн сурагчийн оноо (21/51 дэх)
                next_score = ordered.iloc[quota_list]['score']

                if cutoff_score == next_score:
                    # Ижил оноотой бол тэр оноотой бүгдийг хасна
                    selected_list = ordered[ordered['score'] > cutoff_score].copy()
                else:
                    # Ялгаатай бол эхний 20/50-г авна
                    selected_list = ordered.head(quota_list).copy()

            selected_list['selection_type'] = '2.1 эрх жагсаалтаас'

            result.append(selected_list)

    # --- Нэмэлт эрх олгох (Excel файлаас уншсан тохиргоогоор) ---
    if additional_quota_config is not None and not additional_quota_config.empty:
        # Жагсаалтаас эрх авсан сурагчдын ID-г цуглуулах
        selected_user_ids = set()
        for res_df in result:
            selected_user_ids.update(res_df['user_id'].tolist())

        # Ангиллалын багануудыг тодорхойлох (region_id-аас бусад бүх багана)
        category_columns = [col for col in additional_quota_config.columns if col != 'region_id']

        # Тохиргооны мөр бүрээр (аймаг бүрээр) ажиллах
        for idx, row in additional_quota_config.iterrows():
            region_id = int(row['region_id'])

            # Ангилал бүрээр шалгах (динамик)
            for category in category_columns:
                if pd.notna(row[category]) and row[category] > 0:
                    threshold_score = float(row[category])

                    # Тухайн аймаг, ангиллалын сурагчдыг сонгох
                    mask = (
                        (df['region_id'] == region_id) &
                        (df['category'] == category) &
                        (df['score'] >= threshold_score) &
                        (~df['user_id'].isin(selected_user_ids))  # Жагсаалтаас эрх аваагүй
                    )

                    additional_selected = df[mask].copy()

                    if len(additional_selected) > 0:
                        additional_selected['selection_type'] = '2.1 эрх нэмэлтээр'
                        result.append(additional_selected)

                        # Нэмэлт эрх авсан сурагчдыг мөн цуглуулах (давхардуулахгүй байх)
                        selected_user_ids.update(additional_selected['user_id'].tolist())

    if not result:
        return pd.DataFrame()

    return pd.concat(result).reset_index(drop=True)


def create_round2_groups_and_assign_students(category_to_olympiad, selected_df, stdout):
    """
    Round 2 группүүд үүсгэж, сурагчдыг автоматаар нэмнэ.

    Аймаг + олимпиад бүрээр:
    1. Олимпиадад бүлэг байгаа эсэхийг шалгах
    2. Байхгүй бол Group үүсгэх: Round2_{province_id}_{olympiad_id}
    3. Байвал түүнийг ашиглах
    4. Эрх авсан сурагчдыг группт нэмэх

    Args:
        category_to_olympiad: dict {category: round1_olympiad_id}
        selected_df: DataFrame with selected students
        stdout: Command stdout for logging

    Returns:
        dict with statistics
    """
    from django.contrib.auth.models import User
    from olympiad.utils.group_management import get_or_create_round2_group

    stats = {
        'groups_created': 0,
        'groups_reused': 0,
        'students_added': 0,
        'olympiads_linked': 0,
    }

    # Аймаг + олимпиад бүрээр ажиллах
    for province_id in selected_df['region_id'].unique():
        province_students = selected_df[selected_df['region_id'] == province_id]

        for round1_olympiad_id in province_students['olympiad_id'].unique():
            olympiad_students = province_students[
                province_students['olympiad_id'] == round1_olympiad_id
            ]

            try:
                round1_olympiad = Olympiad.objects.get(id=round1_olympiad_id)
                round2_olympiad = round1_olympiad.next_round

                if not round2_olympiad:
                    stdout.write(f'  ⚠ Олимпиад ID={round1_olympiad_id}-д next_round тохируулаагүй')
                    continue

                # Олимпиадад бүлэг байгаа эсэхийг шалгаад, байхгүй бол үүсгэх
                group, created = get_or_create_round2_group(round2_olympiad, province_id)

                if created:
                    stats['groups_created'] += 1
                    stdout.write(f'  ✓ Групп үүслээ: {group.name}')
                else:
                    stats['groups_reused'] += 1
                    stdout.write(f'  ↻ Групп ашигласан: {group.name}')

                # Олимпиад бүлэгтэй холбогдсоныг баталгаажуулах
                if not round2_olympiad.group:
                    round2_olympiad.group = group
                    round2_olympiad.save(update_fields=['group'])
                    stats['olympiads_linked'] += 1

                # Сурагчдыг группт нэмэх
                student_ids = olympiad_students['user_id'].tolist()
                added_count = 0
                for user_id in student_ids:
                    try:
                        user = User.objects.get(id=user_id)
                        # Аль хэдийн группт байгаа эсэхийг шалгах
                        if not group.user_set.filter(id=user_id).exists():
                            group.user_set.add(user)
                            added_count += 1
                            stats['students_added'] += 1
                    except User.DoesNotExist:
                        stdout.write(f'  ⚠ Хэрэглэгч ID={user_id} олдсонгүй')
                        pass

                stdout.write(
                    f'    → {added_count}/{len(student_ids)} шинээр нэмэгдсэн сурагч | '
                    f'Олимпиад: {round2_olympiad.name} (ID={round2_olympiad.id})'
                )

            except Olympiad.DoesNotExist:
                stdout.write(f'  ✗ Олимпиад ID={round1_olympiad_id} олдсонгүй')
                continue

    return stats


class Command(BaseCommand):
    help = '''2-р давааны 1-р шатны эрх олгох сурагчдыг сонгоно.

    Жишээ:
      # Dry-run хийж үр дүнг харах
      python manage.py first_to_second_by_ranking --config-file additional_quota.xlsx --dry-run

      # Өгөгдөл хадгалах
      python manage.py first_to_second_by_ranking --config-file additional_quota.xlsx

    Дэлгэрэнгүй: ADDITIONAL_QUOTA_GUIDE.md, QUICK_START.md
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            '--config-file',
            type=str,
            required=True,
            help='Тохиргооны Excel файлын зам (олимпиадын ID + нэмэлт эрхийн тохиргоо)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Өгөгдөл хадгалахгүй, зөвхөн үр дүнг харуулна.',
        )

    def handle(self, *args, **options):
        config_file = options['config_file']
        dry_run = options['dry_run']

        # Excel файлаас олимпиадын ID болон нэмэлт эрхийн тохиргоо уншиж авах
        try:
            category_to_olympiad, quota_config = read_quota_config_file(config_file)
            self.stdout.write(self.style.SUCCESS(f'✓ Тохиргоо уншигдлаа: {config_file}'))
            self.stdout.write(f'  Ангилал → Олимпиад: {category_to_olympiad}')
            if quota_config is not None:
                self.stdout.write(f'  Нэмэлт эрхийн тохиргоо: {len(quota_config)} аймаг/дүүрэг\n')
        except Exception as e:
            raise CommandError(f'Тохиргооны файл уншихад алдаа: {e}')

        if not category_to_olympiad:
            raise CommandError('Тохиргооны файлд олимпиадын ID байхгүй байна')

        # Олимпиад бүрийг боловсруулж, үр дүнг цуглуулах
        all_selected = []

        for category, olympiad_id in category_to_olympiad.items():
            self.stdout.write(self.style.HTTP_INFO(f'\n{"="*60}'))
            self.stdout.write(self.style.HTTP_INFO(f'Ангилал: {category} | Олимпиад ID: {olympiad_id}'))
            self.stdout.write(self.style.HTTP_INFO(f'{"="*60}\n'))

            try:
                olympiad = Olympiad.objects.get(id=olympiad_id)
            except Olympiad.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'⚠ Олимпиад ID={olympiad_id} олдсонгүй. Алгасав.\n'))
                continue

            self.stdout.write(f'Олимпиад: {olympiad.name}')
            self.stdout.write(f'Түвшин: {olympiad.level.name}')

            # ScoreSheet өгөгдөл татах
            scoresheets = ScoreSheet.objects.filter(
                olympiad_id=olympiad_id,
                is_official=True  # Зөвхөн эрхийн жагсаалтын сургуулиуд
            ).select_related(
                'user__data__province',
                'school'
            )

            if not scoresheets.exists():
                self.stdout.write(self.style.WARNING(f'⚠ Онооны хуудас олдсонгүй. Алгасав.\n'))
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
                    'category': category,  # Энэ олимпиадын ангилал
                    'olympiad_id': olympiad_id,
                    'score': ss.total or 0,
                    'ranking_a_p': ss.ranking_a_p or 99999,
                })

            if not data:
                self.stdout.write(self.style.WARNING(f'⚠ Боловсруулах өгөгдөл олдсонгүй. Алгасав.\n'))
                continue

            df = pd.DataFrame(data)
            self.stdout.write(f'Нийт оролцогч: {len(df)}')

            # Аймаг, дүүргээр салгаж боловсруулах
            df_aimag = df[df['region_id'] <= 21].copy()
            df_duureg = df[df['region_id'] > 21].copy()

            self.stdout.write(f'  Аймгийн оролцогч: {len(df_aimag)}')
            self.stdout.write(f'  Дүүргийн оролцогч: {len(df_duureg)}')

            # Тухайн ангиллалын нэмэлт эрхийн тохиргоог бэлтгэх
            category_quota_config = None
            if quota_config is not None and category in quota_config.columns:
                category_quota_config = quota_config[['region_id', category]].copy()

            # Сонголт хийх
            selected_aimag = select_next_stage(df_aimag, 'aimag', category_quota_config) if len(df_aimag) > 0 else pd.DataFrame()
            selected_duureg = select_next_stage(df_duureg, 'duureg', category_quota_config) if len(df_duureg) > 0 else pd.DataFrame()

            # Нэгтгэх
            if len(selected_aimag) > 0 and len(selected_duureg) > 0:
                selected = pd.concat([selected_aimag, selected_duureg]).reset_index(drop=True)
            elif len(selected_aimag) > 0:
                selected = selected_aimag
            elif len(selected_duureg) > 0:
                selected = selected_duureg
            else:
                selected = pd.DataFrame()

            if selected.empty:
                self.stdout.write(self.style.WARNING('  Сонгогдсон сурагч байхгүй.\n'))
                continue

            # Энэ олимпиадын үр дүнг цуглуулах
            all_selected.append(selected)

            # Энэ олимпиадын статистик
            self.stdout.write(f'\n  Сонгогдсон: {len(selected)}')

            type_stats = selected.groupby('selection_type').size()
            self.stdout.write('  Төрлөөр:')
            for sel_type, count in type_stats.items():
                self.stdout.write(f'    {sel_type}: {count}')

        # === Бүх олимпиадын үр дүнг нэгтгэх ===
        self.stdout.write(self.style.HTTP_INFO(f'\n{"="*60}'))
        self.stdout.write(self.style.HTTP_INFO('НИЙТ ҮР ДҮН'))
        self.stdout.write(self.style.HTTP_INFO(f'{"="*60}\n'))

        if not all_selected:
            self.stdout.write(self.style.WARNING('Сонгогдсон сурагч байхгүй.'))
            return

        # Бүх олимпиадын үр дүнг нэгтгэх
        combined_selected = pd.concat(all_selected, ignore_index=True)
        self.stdout.write(self.style.SUCCESS(f'Нийт сонгогдсон: {len(combined_selected)}'))

        # Олимпиад бүрээр статистик
        self.stdout.write('\n--- Олимпиад/Ангиллаар ---')
        olympiad_stats = combined_selected.groupby(['category', 'olympiad_id']).size()
        for (cat, oid), count in olympiad_stats.items():
            self.stdout.write(f'  {cat} (ID={oid}): {count}')

        # Төрлөөр статистик
        self.stdout.write('\n--- Төрлөөр ---')
        type_stats = combined_selected.groupby('selection_type').size()
        for sel_type, count in type_stats.items():
            self.stdout.write(f'  {sel_type}: {count}')

        # Аймаг/дүүргээр статистик
        self.stdout.write('\n--- Аймаг/Дүүргээр (топ 10) ---')
        region_stats = combined_selected.groupby('region').size().sort_values(ascending=False).head(10)
        for region, count in region_stats.items():
            self.stdout.write(f'  {region}: {count}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n--dry-run: Өгөгдөл хадгалагдаагүй.'))

            # Сонгогдсон сурагчдын жагсаалт харуулах
            self.stdout.write('\n--- Сонгогдсон сурагчид (эхний 30) ---')
            for idx, row in combined_selected.head(30).iterrows():
                self.stdout.write(f"  {row['category']} | {row['name']} | {row['region']} | {row['score']} | {row['selection_type']}")
        else:
            # Award модельд хадгалах
            self.stdout.write('\n' + self.style.HTTP_INFO('Өгөгдөл хадгалж байна...'))

            # Хуучин "2.1" award-уудыг бүх олимпиадаас устгах
            all_olympiad_ids = list(category_to_olympiad.values())
            deleted_count, _ = Award.objects.filter(
                olympiad_id__in=all_olympiad_ids,
                place__startswith='2.1'
            ).delete()
            if deleted_count:
                self.stdout.write(f'Хуучин {deleted_count} award устгагдлаа.')

            # Шинээр үүсгэх
            created = 0
            for idx, row in combined_selected.iterrows():
                Award.objects.create(
                    olympiad_id=row['olympiad_id'],
                    contestant_id=row['user_id'],
                    place=row['selection_type']
                )
                created += 1

            self.stdout.write(self.style.SUCCESS(f'{created} award үүсгэгдлээ.'))

            # ScoreSheet prizes талбарт мөн тэмдэглэх
            self.stdout.write('ScoreSheet prizes талбарыг шинэчилж байна...')

            # Хуучин 2.1 тэмдэглэгээг арилгах (бүх олимпиадаас)
            for ss in ScoreSheet.objects.filter(olympiad_id__in=all_olympiad_ids):
                if ss.prizes and '2.1' in ss.prizes:
                    # 2.1 агуулсан хэсгийг арилгах
                    parts = [p.strip() for p in ss.prizes.split(',') if '2.1' not in p]
                    ss.prizes = ', '.join(parts) if parts else ''
                    ss.save()

            # Шинээр тэмдэглэх
            updated = 0
            for idx, row in combined_selected.iterrows():
                ss = ScoreSheet.objects.get(id=row['scoresheet_id'])
                selection_type = row['selection_type']
                if ss.prizes:
                    ss.prizes = f"{ss.prizes}, {selection_type}"
                else:
                    ss.prizes = selection_type
                ss.save()
                updated += 1

            self.stdout.write(self.style.SUCCESS(f'{updated} ScoreSheet шинэчлэгдлээ.'))

            # === Round 2 группүүд үүсгэх ===
            self.stdout.write(self.style.HTTP_INFO(f'\n{"="*60}'))
            self.stdout.write(self.style.HTTP_INFO('ROUND 2 ГРУППҮҮД ҮҮСГЭХ'))
            self.stdout.write(self.style.HTTP_INFO(f'{"="*60}\n'))

            group_stats = create_round2_groups_and_assign_students(
                category_to_olympiad,
                combined_selected,
                self.stdout
            )

            self.stdout.write(f'\n✓ Группүүд үүслээ: {group_stats["groups_created"]}')
            self.stdout.write(f'↻ Группүүд ашигласан: {group_stats["groups_reused"]}')
            self.stdout.write(f'👥 Сурагч нэмэгдсэн: {group_stats["students_added"]}')
            self.stdout.write(f'🔗 Олимпиад холбогдсон: {group_stats["olympiads_linked"]}')

            self.stdout.write(self.style.SUCCESS('\n✓ Амжилттай дууслаа!'))
