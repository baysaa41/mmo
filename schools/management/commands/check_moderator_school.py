# accounts/management/commands/check_moderator_school.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db.models import Q

# School загварыг 'schools' апп-аас импорт хийж байна
from schools.models import School

# UserMeta загварыг энэ апп-аас ('accounts') импорт хийж байна
try:
    from ..models import UserMeta
except ImportError:
    # Хэрэв өөр апп-д байвал
    from accounts.models import UserMeta


class Command(BaseCommand):
    help = ("Сургуулийн удирдагч багшийн профайл (UserMeta) дээрх сургууль нь "
            "удирдаж буй сургуультайгаа зөрж буй эсэхийг шалгана.")

    def handle(self, *args, **options):
        self.stdout.write("Сургуулийн удирдагч багш нарын мэдээллийн зөрүүг шалгаж байна...")

        discrepancy_found = False

        # 1. Сургуулийн 'user' талбар нь (удирдагч) NULL биш бүх сургуулийг авна
        all_schools = School.objects.filter(user__isnull=False).select_related(
            'user',
            'user__data',        # UserMeta-г авах
            'user__data__school' # UserMeta доторх сургуулийг авах
        )

        for school in all_schools:
            moderator = school.user
            mobile_info = "(Утас: мэдээлэлгүй)" # Анхдагч утга

            # 2. Удирдагч багшид UserMeta (профайл) үүссэн эсэхийг шалгана
            if hasattr(moderator, 'data') and moderator.data:
                # --- УТАСНЫ ДУГААРЫГ АВАХ ХЭСЭГ ---
                if moderator.data.mobile:
                    mobile_info = f"(Утас: {moderator.data.mobile})" #
                # --- ӨӨРЧЛӨЛТ ДУУСАВ ---

                profile_school = moderator.data.school

                # 4. Профайл дээр сургууль огт бүртгэлгүй (None) эсэхийг шалгах
                if not profile_school:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[ЗӨРҮҮ] Сургууль: '{school.name}' (ID: {school.id})"
                        ) +
                        # --- УТАСНЫ ДУГААРЫГ НЭМСЭН ---
                        f"\n  - Удирдагч: '{moderator.username}' {mobile_info}" +
                        f"\n  - Профайл дээрх сургууль: БАЙХГҮЙ (None)" +
                        f"\n  - Шалтгаан: Удирдаж буй сургууль нь профайл дээр нь бүртгэгдээгүй байна."
                    )
                    discrepancy_found = True
                    continue

                # 5. ГОЛ ШАЛГАЛТ
                if school.id != profile_school.id:
                    self.stdout.write(
                        self.style.ERROR(
                            f"[!!!] НОЦТОЙ ЗӨРҮҮ: '{school.name}' (ID: {school.id})"
                        ) +
                        # --- УТАСНЫ ДУГААРЫГ НЭМСЭН ---
                        f"\n  - Удирдагч: '{moderator.username}' {mobile_info} (ID: {moderator.id})" +
                        f"\n  - Профайл дээрх сургууль: '{profile_school.name}' (ID: {profile_school.id})" +
                        f"\n  - ШАЛТГААН: Удирдаж буй сургууль ({school.name}) болон "
                        f"профайл дээрх сургууль ({profile_school.name}) хоёр зөрж байна."
                    )
                    discrepancy_found = True

            else:
                # UserMeta огт үүсээгүй тохиолдол
                self.stdout.write(
                    self.style.NOTICE(
                        # --- УТАСНЫ ДУГААРЫГ НЭМСЭН ---
                        f"[АНХААРУУЛГА] Сургууль: '{school.name}'-ийн удирдагч '{moderator.username}' {mobile_info}-д "
                        f"профайл (UserMeta) үүсээгүй байна."
                    )
                )
                discrepancy_found = True
                continue

        if not discrepancy_found:
            self.stdout.write(self.style.SUCCESS("\nШалгалт дууслаа. Ямар нэгэн зөрүү олдсонгүй."))
        else:
            self.stdout.write(self.style.WARNING("\nШалгалт дууслаа. Дээрх зөрүүтэй мэдээллүүд олдлоо."))