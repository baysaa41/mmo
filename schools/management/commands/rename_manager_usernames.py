from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
import re


class Command(BaseCommand):
    help = 'Менежер хэрэглэгчдийн username-г s000001 -> s0001 болгож солино'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Үнэхээр солихгүй, зөвхөн юу болохыг харуулна',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # s + 6 орон тоотой хэрэглэгчдийг олох
        all_users = User.objects.filter(username__startswith='s')

        renamed_count = 0
        skipped_count = 0
        error_count = 0

        for user in all_users:
            # s000001 -> s0001 гэх мэт
            match = re.match(r'^s(\d{6})$', user.username)
            if match:
                school_id = int(match.group(1))
                new_username = f's{school_id:04d}'

                if user.username == new_username:
                    # Аль хэдийн зөв формат
                    skipped_count += 1
                    continue

                try:
                    with transaction.atomic():
                        # Шинэ нэр аль хэдийн эзлэгдсэн эсэхийг шалгах
                        if User.objects.filter(username=new_username).exists():
                            self.stdout.write(
                                self.style.WARNING(
                                    f'⚠ Алдаа: {new_username} аль хэдийн байна, {user.username}-г солих боломжгүй'
                                )
                            )
                            error_count += 1
                            continue

                        old_username = user.username

                        if not dry_run:
                            user.username = new_username
                            user.save()

                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✓ Солилоо: {old_username} -> {new_username}'
                                )
                            )
                        else:
                            self.stdout.write(
                                f'[DRY RUN] Солих: {old_username} -> {new_username}'
                            )

                        renamed_count += 1

                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f'✗ Алдаа: {user.username} - {str(e)}'
                        )
                    )

        # Тайлан
        self.stdout.write('\n' + '='*60)
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN MODE - Өгөгдөл хадгалагдаагүй]\n'))

        self.stdout.write(self.style.SUCCESS(f'\n📊 Нийт шалгасан: {all_users.count()}'))
        self.stdout.write(self.style.SUCCESS(f'✓ Солигдсон: {renamed_count}'))
        self.stdout.write(self.style.WARNING(f'⚠ Алгассан: {skipped_count}'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'✗ Алдаатай: {error_count}'))

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\n💡 Үнэхээр ажиллуулахын тулд --dry-run байхгүйгээр дахин ажиллуулна уу.'
                )
            )
