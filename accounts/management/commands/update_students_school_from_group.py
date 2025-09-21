from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from accounts.models import UserMeta, SchoolData
from schools.models import School


class Command(BaseCommand):
    help = ("School.group-т харьяалагдаж буй бүх хэрэглэгчийн "
            "UserMeta.school талбарыг шинэчилж, "
            "харгалзах SchoolData мөрийг устгана.")

    @transaction.atomic
    def handle(self, *args, **options):
        updated_count = 0
        deleted_count = 0

        # Бүх сургуулиудыг шалгах
        for school in School.objects.select_related('group'):
            if not school.group:
                continue  # group байхгүй бол алгасана

            # тухайн сургуулийн group-д байгаа бүх хэрэглэгч
            users_in_group = school.group.user_set.all()

            for user in users_in_group:
                try:
                    meta = UserMeta.objects.get(user=user)
                except UserMeta.DoesNotExist:
                    continue

                # Хэрэв school хоосон бол тухайн сургуулиар шинэчилнэ
                if not meta.school:
                    meta.school = school
                    meta.save(update_fields=['school'])
                    updated_count += 1

                # SchoolData хүснэгтэд байвал устгана
                deleted, _ = SchoolData.objects.filter(user_id=user.id).delete()
                deleted_count += deleted

        self.stdout.write(
            self.style.SUCCESS(
                f"UserMeta.school шинэчилсэн: {updated_count}, "
                f"устгасан SchoolData мөр: {deleted_count}"
            )
        )
