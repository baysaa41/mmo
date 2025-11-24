# olympiad/management/commands/select_next_stage.py

from django.core.management.base import BaseCommand, CommandError
from olympiad.models import ScoreSheet, Olympiad, Award
from django.contrib.auth.models import User
import pandas as pd


def select_next_stage(df, region_type):
    """
    df: columns = ['name', 'school', 'school_id', 'region', 'category', 'score', 'ranking_a_p', 'scoresheet_id', 'user_id']
    region_type: 'aimag' or 'duureg'

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

    if not result:
        return pd.DataFrame()

    return pd.concat(result).reset_index(drop=True)


class Command(BaseCommand):
    help = '2-р давааны 1-р шатны эрх олгох сурагчдыг сонгоно.'

    def add_arguments(self, parser):
        parser.add_argument('--olympiad-id', type=int, required=True, help='Олимпиадын ID')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Өгөгдөл хадгалахгүй, зөвхөн үр дүнг харуулна.',
        )

    def handle(self, *args, **options):
        olympiad_id = options['olympiad_id']
        dry_run = options['dry_run']

        try:
            olympiad = Olympiad.objects.get(id=olympiad_id)
        except Olympiad.DoesNotExist:
            raise CommandError(f'Олимпиад ID={olympiad_id} олдсонгүй.')

        self.stdout.write(f'Олимпиад: {olympiad.name}, {olympiad.level.name}')

        # ScoreSheet өгөгдөл татах
        scoresheets = ScoreSheet.objects.filter(
            olympiad_id=olympiad_id,
            is_official=True  # Зөвхөн эрхийн жагсаалтын сургуулиуд
        ).select_related(
            'user__data__province',
            'school'
        )

        if not scoresheets.exists():
            raise CommandError('Онооны хуудас олдсонгүй.')

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
                'category': olympiad.level.name,
                'score': ss.total or 0,
                'ranking_a_p': ss.ranking_a_p or 99999,
            })

        if not data:
            raise CommandError('Боловсруулах өгөгдөл олдсонгүй.')

        df = pd.DataFrame(data)
        self.stdout.write(f'Нийт оролцогч: {len(df)}')

        # Аймаг, дүүргээр салгаж боловсруулах
        df_aimag = df[df['region_id'] <= 21].copy()
        df_duureg = df[df['region_id'] > 21].copy()

        self.stdout.write(f'Аймгийн оролцогч: {len(df_aimag)}')
        self.stdout.write(f'Дүүргийн оролцогч: {len(df_duureg)}')

        # Сонголт хийх
        selected_aimag = select_next_stage(df_aimag, 'aimag') if len(df_aimag) > 0 else pd.DataFrame()
        selected_duureg = select_next_stage(df_duureg, 'duureg') if len(df_duureg) > 0 else pd.DataFrame()

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
            self.stdout.write(self.style.WARNING('Сонгогдсон сурагч байхгүй.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Нийт сонгогдсон: {len(selected)}'))

        # Төрлөөр статистик
        self.stdout.write('\n--- Төрлөөр статистик ---')
        type_stats = selected.groupby('selection_type').size()
        for sel_type, count in type_stats.items():
            self.stdout.write(f'  {sel_type}: {count}')

        # Аймаг/дүүргээр статистик
        self.stdout.write('\n--- Аймаг/Дүүргийн статистик ---')
        region_stats = selected.groupby('region').size().sort_values(ascending=False)
        for region, count in region_stats.items():
            self.stdout.write(f'  {region}: {count}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n--dry-run: Өгөгдөл хадгалагдаагүй.'))

            # Сонгогдсон сурагчдын жагсаалт харуулах
            self.stdout.write('\n--- Сонгогдсон сурагчид (эхний 50) ---')
            for idx, row in selected.head(50).iterrows():
                self.stdout.write(f"  {row['name']} | {row['school']} | {row['region']} | {row['score']} | {row['selection_type']}")
        else:
            # Award модельд хадгалах

            # Хуучин "2.1" award-уудыг устгах
            deleted_count, _ = Award.objects.filter(
                olympiad_id=olympiad_id,
                place__startswith='2.1'
            ).delete()
            if deleted_count:
                self.stdout.write(f'Хуучин {deleted_count} award устгагдлаа.')

            # Шинээр үүсгэх
            created = 0
            for idx, row in selected.iterrows():
                Award.objects.create(
                    olympiad_id=olympiad_id,
                    contestant_id=row['user_id'],
                    place=row['selection_type']
                )
                created += 1

            self.stdout.write(self.style.SUCCESS(f'\n{created} award үүсгэгдлээ.'))

            # ScoreSheet prizes талбарт мөн тэмдэглэх
            self.stdout.write('ScoreSheet prizes талбарыг шинэчилж байна...')

            # Хуучин 2.1 тэмдэглэгээг арилгах
            for ss in ScoreSheet.objects.filter(olympiad_id=olympiad_id):
                if ss.prizes and '2.1' in ss.prizes:
                    # 2.1 агуулсан хэсгийг арилгах
                    parts = [p.strip() for p in ss.prizes.split(',') if '2.1' not in p]
                    ss.prizes = ', '.join(parts) if parts else ''
                    ss.save()

            # Шинээр тэмдэглэх
            updated = 0
            for idx, row in selected.iterrows():
                ss = ScoreSheet.objects.get(id=row['scoresheet_id'])
                selection_type = row['selection_type']
                if ss.prizes:
                    ss.prizes = f"{ss.prizes}, {selection_type}"
                else:
                    ss.prizes = selection_type
                ss.save()
                updated += 1

            self.stdout.write(self.style.SUCCESS(f'{updated} ScoreSheet шинэчлэгдлээ.'))
