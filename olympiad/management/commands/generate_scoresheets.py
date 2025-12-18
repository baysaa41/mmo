# olympiad/management/commands/generate_scoresheets.py

from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Case, When, Value, IntegerField, OuterRef, Subquery, BooleanField
from olympiad.models import ScoreSheet, Award, Olympiad
from olympiad.utils.data import to_scoresheet
from olympiad.utils.ranking import (
    update_rankings_a, update_rankings_b,
    update_rankings_a_p, update_rankings_b_p,
    update_rankings_a_p_all, update_rankings_b_p_all,
    update_rankings_a_p_u, update_rankings_b_p_u,
    update_rankings_a_z, update_rankings_b_z,
    update_rankings_a_z_all, update_rankings_b_z_all,
    update_rankings_a_z_u, update_rankings_b_z_u
)
from schools.models import School

class Command(BaseCommand):
    help = 'Онооны хуудсыг үүсгэж, бүх эрэмбийг тооцоолно.'

    def add_arguments(self, parser):
        parser.add_argument('olympiad_ids', nargs='+', type=int, help='Олимпиадын ID-ууд')
        parser.add_argument(
            '--force-delete',
            action='store_true',
            help='Шинээр үүсгэхийн өмнө хуучин онооны хуудсыг баталгаажуулалтгүйгээр устгана.',
        )
        parser.add_argument('--log-file', type=str, default='generate_scoresheets_log.txt', help='Log файлын нэр')

    def handle(self, *args, **options):
        olympiad_ids = options['olympiad_ids']
        force_delete = options['force_delete']
        log_file = options['log_file']

        self.stdout.write(f'Олимпиадууд: {olympiad_ids}')
        self.stdout.write(f'Нийт: {len(olympiad_ids)} олимпиад')
        self.stdout.write('=' * 80)

        # Статистик хадгалах
        total_stats = {
            'processed': 0,
            'failed': 0,
            'total_scoresheets': 0,
            'total_official': 0,
            'start_time': datetime.now(),
            'olympiad_details': [],  # Олимпиад бүрийн дэлгэрэнгүй
            'errors': [],  # Алдаанууд
        }

        # Олимпиад бүрээр боловсруулах
        for i, olympiad_id in enumerate(olympiad_ids, 1):
            self.stdout.write(f'\n[{i}/{len(olympiad_ids)}] Олимпиад ID={olympiad_id} боловсруулж байна...')
            self.stdout.write('-' * 80)

            olympiad_detail = {
                'olympiad_id': olympiad_id,
                'success': False,
                'error': None,
            }

            try:
                self.process_olympiad(olympiad_id, force_delete, total_stats, olympiad_detail)
                total_stats['processed'] += 1
                olympiad_detail['success'] = True
                self.stdout.write(self.style.SUCCESS(f'✅ Олимпиад ID={olympiad_id} амжилттай боловсруулагдлаа.'))
            except Exception as e:
                total_stats['failed'] += 1
                olympiad_detail['error'] = str(e)
                total_stats['errors'].append({
                    'olympiad_id': olympiad_id,
                    'error': str(e)
                })
                self.stdout.write(self.style.ERROR(f'❌ Олимпиад ID={olympiad_id} алдаа: {e}'))
            finally:
                total_stats['olympiad_details'].append(olympiad_detail)

        # Эцсийн тайлан
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('📊 ЭЦСИЙН ТАЙЛАН'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Нийт олимпиад: {len(olympiad_ids)}')
        self.stdout.write(f'✅ Амжилттай: {total_stats["processed"]}')
        self.stdout.write(f'❌ Алдаатай: {total_stats["failed"]}')
        self.stdout.write(f'📄 Нийт ScoreSheet: {total_stats["total_scoresheets"]}')
        self.stdout.write(f'🏫 Official ScoreSheet: {total_stats["total_official"]}')
        self.stdout.write('=' * 80)

        # Log файл бичих
        self.write_log_file(log_file, olympiad_ids, total_stats, force_delete)
        self.stdout.write(self.style.SUCCESS(f'\n💾 Log файл бичигдлээ: {log_file}'))

    def process_olympiad(self, olympiad_id, force_delete, total_stats, olympiad_detail):
        """Нэг олимпиадыг боловсруулах"""

        # Олимпиадын нэр авах
        try:
            olympiad = Olympiad.objects.get(id=olympiad_id)
            olympiad_detail['olympiad_name'] = olympiad.name
        except Olympiad.DoesNotExist:
            raise CommandError(f'Олимпиад ID={olympiad_id} олдсонгүй')

        if force_delete:
            self.stdout.write(self.style.WARNING(f'  --force-delete туг ашигласан тул хуучин онооны хуудсыг устгаж байна...'))
            deleted_count, _ = ScoreSheet.objects.filter(olympiad_id=olympiad_id).delete()
            olympiad_detail['deleted_scoresheets'] = deleted_count
            self.stdout.write(self.style.SUCCESS(f'  {deleted_count} хуучин онооны хуудас устгагдлаа.'))

        # 1. Сайжруулсан to_scoresheet функцийг дуудах
        self.stdout.write('  Онооны хуудсыг үүсгэж/шинэчилж байна...')
        try:
            to_scoresheet(olympiad_id)
            scoresheet_count = ScoreSheet.objects.filter(olympiad_id=olympiad_id).count()
            total_stats['total_scoresheets'] += scoresheet_count
            olympiad_detail['scoresheets_created'] = scoresheet_count
            self.stdout.write(self.style.SUCCESS(f'  {scoresheet_count} онооны хуудас үүслээ.'))
        except Exception as e:
            raise CommandError(f'Онооны хуудас үүсгэхэд алдаа гарлаа: {e}')

        # 2. is_official талбарыг сургуулийн official_levels-ээс тогтоох
        self.stdout.write('  is_official талбарыг тогтоож байна...')

        # round=1 дээр л is_official шалгах, бусад тохиолдолд бүх сургуулийг official гэж үзнэ
        if olympiad.round == 1:
            olympiad_level_id = olympiad.level_id

            updated_count = ScoreSheet.objects.filter(
                olympiad_id=olympiad_id,
                school__official_levels__id=olympiad_level_id
            ).update(is_official=True)
            total_stats['total_official'] += updated_count
            olympiad_detail['official_count'] = updated_count

            # Сургуульгүй эсвэл тухайн түвшинд official биш бол False болгох
            ScoreSheet.objects.filter(
                olympiad_id=olympiad_id
            ).exclude(
                school__official_levels__id=olympiad_level_id
            ).update(is_official=False)
            self.stdout.write(self.style.SUCCESS(f'  {updated_count} онооны хуудсанд is_official=True тогтоогдлоо.'))
        else:
            # Бусад шатанд бүх сургуулийг official гэж үзнэ
            updated_count = ScoreSheet.objects.filter(olympiad_id=olympiad_id).update(is_official=True)
            total_stats['total_official'] += updated_count
            olympiad_detail['official_count'] = updated_count
            self.stdout.write(self.style.SUCCESS(f'  Round {olympiad.round}: Бүх {updated_count} онооны хуудас official болгогдлоо.'))

        # 3. Эрэмбийг тооцоолох
        self.stdout.write('  Эрэмбэ тооцоолж байна...')

        # Нийт эрэмбэ
        update_rankings_a(olympiad_id)
        update_rankings_b(olympiad_id)
        self.stdout.write(self.style.SUCCESS('  Улсын нийт эрэмбэ шинэчлэгдлээ.'))

        # Зөвхөн оролцогчид байгаа аймаг, бүсүүдийг олж авах
        active_provinces = ScoreSheet.objects.filter(olympiad_id=olympiad_id, user__data__province__isnull=False).values_list('user__data__province_id', flat=True).distinct()
        active_zones = ScoreSheet.objects.filter(olympiad_id=olympiad_id, user__data__province__zone__isnull=False).values_list('user__data__province__zone_id', flat=True).distinct()

        olympiad_detail['province_count'] = len(active_provinces)
        olympiad_detail['zone_count'] = len(active_zones)

        # Аймгийн эрэмбэ (зөвхөн оролцогчтой аймгуудаар)
        for province_id in active_provinces:
            # Official only
            update_rankings_a_p(olympiad_id, province_id)
            update_rankings_b_p(olympiad_id, province_id)
            # All students
            update_rankings_a_p_all(olympiad_id, province_id)
            update_rankings_b_p_all(olympiad_id, province_id)
            # Unofficial only
            update_rankings_a_p_u(olympiad_id, province_id)
            update_rankings_b_p_u(olympiad_id, province_id)
        self.stdout.write(self.style.SUCCESS(f'  {len(active_provinces)} аймгийн эрэмбэ шинэчлэгдлээ.'))

        # Бүсийн эрэмбэ (зөвхөн оролцогчтой бүсүүдээр)
        for zone_id in active_zones:
            # Official only
            update_rankings_a_z(olympiad_id, zone_id)
            update_rankings_b_z(olympiad_id, zone_id)
            # All students
            update_rankings_a_z_all(olympiad_id, zone_id)
            update_rankings_b_z_all(olympiad_id, zone_id)
            # Unofficial only
            update_rankings_a_z_u(olympiad_id, zone_id)
            update_rankings_b_z_u(olympiad_id, zone_id)
        self.stdout.write(self.style.SUCCESS(f'  {len(active_zones)} бүсийн эрэмбэ шинэчлэгдлээ.'))

        # --- ШАГНАЛ ОЛГОХ ШИНЭ ХЭСЭГ (ОНОВЧЛОГДСОН) ---
        self.stdout.write('  Шагналын мэдээллийг онооны хуудсанд нэмж байна...')

        # Эхлээд тухайн олимпиадын бүх онооны хуудасны шагналыг цэвэрлэх
        ScoreSheet.objects.filter(olympiad_id=olympiad_id).update(prizes=None)

        # Бүх шагналыг нэг query-ээр татах
        all_awards = Award.objects.filter(olympiad_id=olympiad_id).annotate(
            award_order=Case(
                When(place__icontains='алт', then=Value(1)),
                When(place__icontains='мөнгө', then=Value(2)),
                When(place__icontains='хүрэл', then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
        ).order_by('contestant_id', 'award_order', 'place')

        # Оролцогчоор бүлэглэх
        from collections import defaultdict
        awards_by_user = defaultdict(list)
        for award in all_awards:
            awards_by_user[award.contestant_id].append(award.place)

        # ScoreSheet-үүдийг шинэчлэх
        score_sheets = ScoreSheet.objects.filter(olympiad_id=olympiad_id)
        updates = []
        for sheet in score_sheets:
            if sheet.user_id in awards_by_user:
                sheet.prizes = ", ".join(awards_by_user[sheet.user_id])
                updates.append(sheet)

        # Bulk update
        if updates:
            ScoreSheet.objects.bulk_update(updates, ['prizes'], batch_size=1000)

        olympiad_detail['awards_count'] = len(updates)
        self.stdout.write(self.style.SUCCESS(f'  {len(updates)} хүнд шагналын мэдээлэл нэмэгдлээ.'))

    def write_log_file(self, log_file, olympiad_ids, total_stats, force_delete):
        """Log файл бичих"""
        try:
            duration = (datetime.now() - total_stats['start_time']).total_seconds()

            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"=== GENERATE SCORESHEETS LOG - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                f.write(f"Force Delete: {'Yes' if force_delete else 'No'}\n")
                f.write(f"Хугацаа: {duration:.1f} секунд\n\n")

                f.write(f"{'='*80}\n")
                f.write(f"НИЙТ ТАЙЛАН\n")
                f.write(f"{'='*80}\n")
                f.write(f"Нийт олимпиад: {len(olympiad_ids)}\n")
                f.write(f"✅ Амжилттай: {total_stats['processed']}\n")
                f.write(f"❌ Алдаатай: {total_stats['failed']}\n")
                f.write(f"📄 Нийт ScoreSheet: {total_stats['total_scoresheets']}\n")
                f.write(f"🏫 Official ScoreSheet: {total_stats['total_official']}\n\n")

                # Олимпиад бүрийн дэлгэрэнгүй
                f.write(f"{'='*80}\n")
                f.write(f"ОЛИМПИАД БҮРИЙН ДЭЛГЭРЭНГҮЙ\n")
                f.write(f"{'='*80}\n\n")

                for detail in total_stats['olympiad_details']:
                    f.write(f"Олимпиад ID: {detail['olympiad_id']}\n")
                    if 'olympiad_name' in detail:
                        f.write(f"Нэр: {detail['olympiad_name']}\n")
                    f.write(f"Статус: {'✅ Амжилттай' if detail['success'] else '❌ Амжилтгүй'}\n")

                    if detail['success']:
                        if 'deleted_scoresheets' in detail:
                            f.write(f"  Устгасан ScoreSheet: {detail.get('deleted_scoresheets', 0)}\n")
                        f.write(f"  Үүссэн ScoreSheet: {detail.get('scoresheets_created', 0)}\n")
                        f.write(f"  Official ScoreSheet: {detail.get('official_count', 0)}\n")
                        f.write(f"  Аймаг: {detail.get('province_count', 0)}\n")
                        f.write(f"  Бүс: {detail.get('zone_count', 0)}\n")
                        f.write(f"  Шагналтай: {detail.get('awards_count', 0)}\n")
                    else:
                        f.write(f"  Алдаа: {detail.get('error', 'Тодорхойгүй')}\n")

                    f.write(f"{'-'*40}\n")

                # Алдаанууд
                if total_stats['errors']:
                    f.write(f"\n{'='*80}\n")
                    f.write(f"АЛДААНУУД ({len(total_stats['errors'])} тохиолдол)\n")
                    f.write(f"{'='*80}\n")
                    for err in total_stats['errors']:
                        f.write(f"Олимпиад ID: {err['olympiad_id']}\n")
                        f.write(f"Алдаа: {err['error']}\n")
                        f.write(f"{'-'*40}\n")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Log файл бичихэд алдаа: {e}"))