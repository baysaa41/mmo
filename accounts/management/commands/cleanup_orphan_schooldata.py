from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import SchoolData

class Command(BaseCommand):
    help = "User хүснэгтэд байхгүй user_id-тэй SchoolData мөрүүдийг устгана"

    def handle(self, *args, **options):
        # Бүх user_id-г нэг дор авах
        existing_ids = set(User.objects.values_list('id', flat=True))

        # SchoolData дотроос байхгүй user_id-г сонгох
        orphan_qs = SchoolData.objects.exclude(user_id__in=existing_ids)

        total = orphan_qs.count()
        orphan_qs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"User хүснэгтэд байхгүй {total} SchoolData мөрийг устгалаа."
            )
        )
