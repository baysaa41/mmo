from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from schools.models import School
from accounts.models import UserMeta
from django.utils.crypto import get_random_string


class Command(BaseCommand):
    help = 'Сургууль бүрт менежер хэрэглэгч үүсгэнэ'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Үнэхээр үүсгэхгүй, зөвхөн юу болохыг харуулна',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        schools = School.objects.select_related('user', 'user__data', 'province', 'manager').all()

        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0

        for school in schools:
            # Сургуулийн ID-г 4 оронтой болгох (s0001 гэх мэт)
            username = f's{school.id:04d}'

            try:
                with transaction.atomic():
                    # Хэрэглэгч аль хэдийн байгаа эсэхийг шалгах
                    user, created = User.objects.get_or_create(
                        username=username,
                        defaults={
                            'first_name': 'Менежер',
                            'last_name': f"{school.province.name} {school.name}",
                        }
                    )

                    if created:
                        # Шинэ хэрэглэгч үүссэн бол
                        # Бүртгэгч багшийн и-мэйл, гар утсыг хуулах
                        if school.user:
                            user.email = school.user.email or ''
                            # Анхны нууц үг үүсгэх
                            temp_password = get_random_string(20)
                            user.set_password(temp_password)
                        else:
                            user.set_unusable_password()

                        user.save()

                        # UserMeta үүсгэх
                        if school.user and hasattr(school.user, 'data'):
                            moderator_data = school.user.data
                            meta_data = {
                                'user': user,
                                'school': school,
                                'province': school.province,
                            }
                            # Mobile нь тоо байх ёстой, хоосон бол None
                            if moderator_data.mobile:
                                meta_data['mobile'] = moderator_data.mobile
                            if moderator_data.gender:
                                meta_data['gender'] = moderator_data.gender
                            if moderator_data.grade:
                                meta_data['grade'] = moderator_data.grade
                            if moderator_data.level:
                                meta_data['level'] = moderator_data.level

                            UserMeta.objects.create(**meta_data)
                        else:
                            # Бүртгэгч багш байхгүй бол үндсэн мэдээллээр үүсгэх
                            UserMeta.objects.create(
                                user=user,
                                school=school,
                                province=school.province,
                            )

                        if not dry_run:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✓ Үүсгэв: {username} - {school.name} ({school.province.name})'
                                )
                            )
                        else:
                            self.stdout.write(
                                f'[DRY RUN] Үүсгэх: {username} - {school.name}'
                            )
                        created_count += 1
                    else:
                        # Хэрэглэгч аль хэдийн байгаа
                        if not dry_run:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'⚠ Аль хэдийн байна: {username} - {school.name}'
                                )
                            )
                        updated_count += 1

                    # Сургуулийн менежер болгох
                    if not school.manager or school.manager != user:
                        if not dry_run:
                            school.manager = user
                            school.save()
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'  → {school.name}-д менежер болгов'
                                )
                            )
                        else:
                            self.stdout.write(
                                f'[DRY RUN] {school.name}-д менежер болгох'
                            )

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ Алдаа: {school.name} - {str(e)}'
                    )
                )
                # Continue to next school
                continue

        # Тайлан
        self.stdout.write('\n' + '='*60)
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN MODE - Өгөгдөл хадгалагдаагүй]\n'))

        self.stdout.write(self.style.SUCCESS(f'\n📊 Нийт сургууль: {schools.count()}'))
        self.stdout.write(self.style.SUCCESS(f'✓ Шинэ үүсгэсэн: {created_count}'))
        self.stdout.write(self.style.WARNING(f'⚠ Аль хэдийн байгаа: {updated_count}'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'✗ Алдаатай: {error_count}'))

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\n💡 Үнэхээр ажиллуулахын тулд --dry-run байхгүйгээр дахин ажиллуулна уу.'
                )
            )
