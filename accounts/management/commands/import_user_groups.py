from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
import csv

class Command(BaseCommand):
    help = "auth_user_groups CSV-ээс хэрэглэгч-группийн холбоог сэргээнэ."

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Импортлох CSV файлын зам')

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        added_count = 0
        skipped_user = 0
        skipped_group = 0

        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                user_id = row.get('user_id')
                group_id = row.get('group_id')

                if not user_id or not group_id:
                    continue

                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    skipped_user += 1
                    continue

                try:
                    group = Group.objects.get(id=group_id)
                except Group.DoesNotExist:
                    skipped_group += 1
                    continue

                # Групп давхар нэмэгдэхээс сэргийлэх
                if not user.groups.filter(id=group.id).exists():
                    user.groups.add(group)
                    added_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"{added_count} холбоо сэргээгдлээ. "
            f"{skipped_user} мөр хэрэглэгч олдсонгүй, "
            f"{skipped_group} мөр групп олдсонгүй."
        ))
