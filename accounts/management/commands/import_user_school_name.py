from django.core.management.base import BaseCommand
from accounts.models import UserMeta
import csv

class Command(BaseCommand):
    help = "CSV файлаас user_school_name баганыг UserMeta руу импортолно."

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Импорт хийх CSV файлын зам')

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        updated_count = 0
        skipped_count = 0

        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                user_id = row.get('user_id')
                name = row.get('user_school_name')
                if not user_id or not name:
                    skipped_count += 1
                    continue
                try:
                    um = UserMeta.objects.get(user_id=user_id)
                except UserMeta.DoesNotExist:
                    skipped_count += 1
                    continue

                um.user_school_name = name.strip()
                um.save(update_fields=['user_school_name'])
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{updated_count} мөр импортлогдож, {skipped_count} мөр алгасагдлаа."
            )
        )
