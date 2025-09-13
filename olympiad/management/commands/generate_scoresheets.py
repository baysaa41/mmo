# olympiad/management/commands/generate_scoresheets.py

from django.core.management.base import BaseCommand, CommandError
from olympiad.models import Olympiad, ScoreSheet
from accounts.models import Province, Zone
# data.py файлаас to_scoresheet функцийг импортлох
from olympiad.utils.data import to_scoresheet
# ranking.py файлаас эрэмбэ тооцоолох функцүүдийг импортлох
from olympiad.utils.ranking import (
    update_rankings_a, update_rankings_b,
    update_rankings_a_p, update_rankings_b_p,
    update_rankings_a_z, update_rankings_b_z
)

class Command(BaseCommand):
    help = 'Generates ScoreSheet entries using to_scoresheet function and then calculates all rankings.'

    def add_arguments(self, parser):
            parser.add_argument('olympiad_id', type=int, help='...')
            # Устгах үйлдлийг алгасах --no-delete гэсэн сонголт нэмэх
            parser.add_argument(
                '--no-delete',
                action='store_true',
                help='Do not delete existing scoresheets before generating new ones.',
            )

    def handle(self, *args, **options):
        olympiad_id = options['olympiad_id']
        # ...

        # --no-delete сонголт хийгээгүй үед л устгах
        if not options['no_delete']:
            self.stdout.write(self.style.WARNING('Deleting old scoresheets to prevent stale data...'))

            # Баталгаажуулалт асуух
            confirmation = input('Are you sure you want to delete all scoresheets for this olympiad? (yes/no): ')
            if confirmation.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Operation cancelled by user.'))
                return

            deleted_count, _ = ScoreSheet.objects.filter(olympiad_id=olympiad_id).delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} old scoresheet entries.'))

        # 1. to_scoresheet функцийг дуудаж ScoreSheet-үүдийг үүсгэх
        self.stdout.write('Generating scoresheets using to_scoresheet function...')
        try:
            to_scoresheet(olympiad_id)
            self.stdout.write(self.style.SUCCESS('All scoresheets generated/updated successfully.'))
        except Exception as e:
            raise CommandError(f'An error occurred during scoresheet generation: {e}')

        # 2. Эрэмбийг тооцоолох (ranking.py-г ашиглах)
        self.stdout.write('Calculating rankings...')

        # Нийт эрэмбэ
        update_rankings_a(olympiad_id)
        update_rankings_b(olympiad_id)
        self.stdout.write(self.style.SUCCESS('... Overall rankings updated.'))

        # Аймгийн эрэмбэ
        provinces = Province.objects.all()
        for province in provinces:
            update_rankings_a_p(olympiad_id, province.id)
            update_rankings_b_p(olympiad_id, province.id)
        self.stdout.write(self.style.SUCCESS('... Provincial rankings updated.'))

        # Бүсийн эрэмбэ
        zones = Zone.objects.all()
        for zone in zones:
            update_rankings_a_z(olympiad_id, zone.id)
            update_rankings_b_z(olympiad_id, zone.id)
        self.stdout.write(self.style.SUCCESS('... Zonal rankings updated.'))

        self.stdout.write(self.style.SUCCESS('All tasks completed!'))