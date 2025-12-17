from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from accounts.models import UserMeta
from schools.models import School
from collections import defaultdict


class Command(BaseCommand):
    help = ("School.group-д харьяалагдаж буй хэрэглэгчдийн UserMeta.school талбарыг шинэчилнэ. "
            "Зөвхөн 1 сургуулийн group-д харьяалагдаж буй хэрэглэгчдийг шинэчилнэ, "
            "олон сургуульд харьяалагдсан бол өөрчлөхгүй.")

    @transaction.atomic
    def handle(self, *args, **options):
        updated_count = 0
        skipped_multiple = 0

        # Хэрэглэгч -> [сургуулиуд] толь бичиг үүсгэх
        user_schools = defaultdict(list)

        # Бүх сургуулиудыг шалгаж, хэрэглэгч бүр ямар сургуулиудад байгааг тодорхойлох
        for school in School.objects.select_related('group'):
            if not school.group:
                continue

            users_in_group = school.group.user_set.all()
            for user in users_in_group:
                user_schools[user.id].append(school)

        # Одоо хэрэглэгч бүрийг шалгаад шинэчлэх
        for user_id, schools in user_schools.items():
            if len(schools) > 1:
                # Олон сургуульд харьяалагдсан бол алгасах
                skipped_multiple += 1
                user = User.objects.get(id=user_id)
                school_names = ', '.join([s.name for s in schools])
                self.stdout.write(
                    self.style.WARNING(
                        f"Алгасав: {user.username} нь {len(schools)} сургуульд байна: {school_names}"
                    )
                )
                continue

            # Зөвхөн 1 сургуульд байвал шинэчлэх
            school = schools[0]
            try:
                meta = UserMeta.objects.get(user_id=user_id)
                if not meta.school:
                    meta.school = school
                    # Сургуулийн дүүргийн мэдээллийг хэрэглэгчийн дүүрэг болгож оноох
                    if school.province:
                        meta.province = school.province
                    meta.save(update_fields=['school', 'province'])
                    updated_count += 1
                    province_name = school.province.name if school.province else 'N/A'
                    self.stdout.write(f"Шинэчилсэн: {meta.user.username} → {school.name} ({province_name})")
            except UserMeta.DoesNotExist:
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"\nУспех: {updated_count} хэрэглэгчийн сургуулийг шинэчиллээ\n"
                f"Алгасав: {skipped_multiple} хэрэглэгч олон сургуульд харьяалагдсан байна"
            )
        )
