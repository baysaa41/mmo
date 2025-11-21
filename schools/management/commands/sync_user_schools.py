from django.core.management.base import BaseCommand
from django.db import transaction
from schools.models import School
from accounts.models import UserMeta

class Command(BaseCommand):
    help = 'Хэрэглэгчийн группт хамаарах сургуулийг UserMeta модел дээрх school талбарт тохируулна.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Хэрэглэгчийн сургуулийг синхрончлох процессыг эхлүүлж байна...'))

        # Зөвхөн групп оноогдсон сургуулиудыг авах
        schools_with_groups = School.objects.filter(group__isnull=False)

        if not schools_with_groups.exists():
            self.stdout.write(self.style.WARNING('Бүлэг оноогдсон сургууль олдсонгүй. Процесс зогслоо.'))
            return

        # Хэрэглэгчээс баталгаажуулалт авах
        confirm = input(f'{schools_with_groups.count()} сургуулийн мэдээллийг шинэчлэх гэж байна. Үргэлжлүүлэх үү? (yes/no): ')
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.WARNING('Процесс цуцлагдлаа.'))
            return

        updated_user_count = 0
        updated_school_count = 0

        try:
            # Бүх үйлдлийг нэг transaction дотор хийснээр алдаа гарвал бүх өөрчлөлт буцна
            with transaction.atomic():
                for school in schools_with_groups:
                    # Сургуулийн группт хамаарах бүх хэрэглэгчийн ID-г авах
                    user_ids_in_group = school.group.user_set.values_list('id', flat=True)

                    if not user_ids_in_group:
                        continue # Хэрэв группт хэрэглэгч байхгүй бол алгасах

                    # UserMeta-г олон тоогоор, нэг дор шинэчлэх (маш хурдан)
                    num_updated = UserMeta.objects.filter(user_id__in=user_ids_in_group).update(school=school,province=school.province)

                    if num_updated > 0:
                        self.stdout.write(f'- {school.name}: {num_updated} хэрэглэгчийг шинэчиллээ.')
                        updated_user_count += num_updated
                        updated_school_count += 1
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Алдаа гарлаа: {e}'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'\nПроцесс амжилттай дууслаа. Нийт {updated_school_count} сургуулийн {updated_user_count} хэрэглэгчийн мэдээллийг шинэчиллээ.'
        ))