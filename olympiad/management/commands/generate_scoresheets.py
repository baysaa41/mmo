# olympiad/management/commands/generate_scoresheets.py

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Case, When, Value, IntegerField
from olympiad.models import ScoreSheet, Award
from olympiad.utils.data import to_scoresheet
from olympiad.utils.ranking import (
    update_rankings_a, update_rankings_b,
    update_rankings_a_p, update_rankings_b_p,
    update_rankings_a_z, update_rankings_b_z
)

class Command(BaseCommand):
    help = 'Онооны хуудсыг үүсгэж, бүх эрэмбийг тооцоолно.'

    def add_arguments(self, parser):
        parser.add_argument('--olympiad-id', type=int, required=True, help='Онооны хуудас үүсгэх Олимпиадын ID')
        parser.add_argument(
            '--force-delete',
            action='store_true',
            help='Шинээр үүсгэхийн өмнө хуучин онооны хуудсыг баталгаажуулалтгүйгээр устгана.',
        )

    def handle(self, *args, **options):
        olympiad_id = options['olympiad_id']

        if options['force_delete']:
            self.stdout.write(self.style.WARNING(f'--force-delete туг ашигласан тул Олимпиад ID={olympiad_id}-д хамаарах хуучин онооны хуудсыг устгаж байна...'))
            deleted_count, _ = ScoreSheet.objects.filter(olympiad_id=olympiad_id).delete()
            self.stdout.write(self.style.SUCCESS(f'{deleted_count} хуучин онооны хуудас устгагдлаа.'))

        # 1. Сайжруулсан to_scoresheet функцийг дуудах
        self.stdout.write('Онооны хуудсыг үүсгэж/шинэчилж байна...')
        try:
            to_scoresheet(olympiad_id)
            self.stdout.write(self.style.SUCCESS('Онооны хуудсууд амжилттай үүслээ.'))
        except Exception as e:
            raise CommandError(f'Онооны хуудас үүсгэхэд алдаа гарлаа: {e}')

        # 2. Эрэмбийг тооцоолох
        self.stdout.write('Эрэмбэ тооцоолж байна...')

        # Нийт эрэмбэ
        update_rankings_a(olympiad_id)
        update_rankings_b(olympiad_id)
        self.stdout.write(self.style.SUCCESS('... Улсын нийт эрэмбэ шинэчлэгдлээ.'))

        # Зөвхөн оролцогчид байгаа аймаг, бүсүүдийг олж авах
        active_provinces = ScoreSheet.objects.filter(olympiad_id=olympiad_id, user__data__province__isnull=False).values_list('user__data__province_id', flat=True).distinct()
        active_zones = ScoreSheet.objects.filter(olympiad_id=olympiad_id, user__data__province__zone__isnull=False).values_list('user__data__province__zone_id', flat=True).distinct()

        # Аймгийн эрэмбэ (зөвхөн оролцогчтой аймгуудаар)
        for province_id in active_provinces:
            update_rankings_a_p(olympiad_id, province_id)
            update_rankings_b_p(olympiad_id, province_id)
        self.stdout.write(self.style.SUCCESS(f'... {len(active_provinces)} аймгийн эрэмбэ шинэчлэгдлээ.'))

        # Бүсийн эрэмбэ (зөвхөн оролцогчтой бүсүүдээр)
        for zone_id in active_zones:
            update_rankings_a_z(olympiad_id, zone_id)
            update_rankings_b_z(olympiad_id, zone_id)
        self.stdout.write(self.style.SUCCESS(f'... {len(active_zones)} бүсийн эрэмбэ шинэчлэгдлээ.'))

        # --- ШАГНАЛ ОЛГОХ ШИНЭ ХЭСЭГ ---
        self.stdout.write('Шагналын мэдээллийг онооны хуудсанд нэмж байна...')

        # Эхлээд тухайн олимпиадын бүх онооны хуудасны шагналыг цэвэрлэх
        ScoreSheet.objects.filter(olympiad_id=olympiad_id).update(prizes=None)

        score_sheets = ScoreSheet.objects.filter(olympiad_id=olympiad_id)

        for sheet in score_sheets:
            # Тухайн сурагчийн, тухайн олимпиадаас авсан бүх шагналыг олох
            awards = Award.objects.filter(
                contestant=sheet.user,
                olympiad_id=olympiad_id
            ).annotate(
                # Медалийг эхэнд эрэмбэлэхийн тулд түр талбар үүсгэх
                award_order=Case(
                    When(place__icontains='алт', then=Value(1)),
                    When(place__icontains='мөнгө', then=Value(2)),
                    When(place__icontains='хүрэл', then=Value(3)),
                    default=Value(4),
                    output_field=IntegerField(),
                )
            ).order_by('award_order', 'place')

            if awards.exists():
                # Шагналуудын нэрийг жагсаалт болгож, таслалаар нэгтгэх
                prize_list = [award.place for award in awards]
                sheet.prizes = ", ".join(prize_list)
                sheet.save()

        self.stdout.write(self.style.SUCCESS('... Шагналын мэдээлэл амжилттай нэмэгдлээ.'))
        self.stdout.write(self.style.SUCCESS('\nҮйлдэл бүрэн дууслаа!'))