# schools/management/commands/fixduplicateschools.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from schools.models import School
from django.db.models import Count

class Command(BaseCommand):
    help = """
    Finds groups linked to multiple schools and fixes the conflict by keeping the school
    with the highest ID and PERMANENTLY DELETING the others.
    
    WARNING: This is a destructive operation. Backup your database before running.
    You MUST use the --confirm flag to proceed.
    """

    def add_arguments(self, parser):
        # Аюулгүй байдлын үүднээс заавал --confirm гэж бичиж байж ажилладаг болгох
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Энэ комманд өгөгдөл устгахыг зөвшөөрч буйг баталгаажуулах.',
        )

    def handle(self, *args, **options):
        # --confirm гэсэн сонголт өгөөгүй бол коммандыг ажиллуулахгүй
        if not options['confirm']:
            self.stdout.write(self.style.ERROR(
                "🛑  АНХААРУУЛГА: Энэ комманд Сургуулийн бичлэгийг БҮРМӨСӨН УСТГАНА."
            ))
            self.stdout.write(self.style.WARNING(
                "Үргэлжлүүлэхийн тулд '--confirm' гэсэн нэмэлт сонголтыг ашиглана уу."
            ))
            self.stdout.write(self.style.WARNING(
                "Жишээ: python manage.py fixduplicateschools --confirm"
            ))
            return

        self.stdout.write(self.style.WARNING(
            "🔥  Сургуулийн илүүдэл бичлэгийг устгах үйлдэл эхэллээ..."
        ))

        # 1. Нэгээс олон сургуультай холбогдсон бүлгүүдийн ID-г олох
        duplicate_group_ids = School.objects.values('group_id').annotate(
            group_count=Count('group_id')
        ).filter(
            group_count__gt=1
        ).values_list('group_id', flat=True)

        if not list(duplicate_group_ids):
            self.stdout.write(self.style.SUCCESS("✔️  Зөрчилтэй холболт олдсонгүй."))
            return

        self.stdout.write(f"⚠️  Олдсон {len(list(duplicate_group_ids))} зөрчилтэй бүлгийн холболтыг засварлаж байна...")

        total_deleted = 0
        # 2. Зөрчилтэй бүлэг тус бүрээр давтах
        for group_id in duplicate_group_ids:
            if group_id is None:
                continue

            try:
                group = Group.objects.get(id=group_id)
                self.stdout.write(self.style.NOTICE(f"\n- Зөрчлийг арилгаж байна: '{group.name}' (ID: {group.id})"))

                conflicting_schools = School.objects.filter(group_id=group_id)
                school_to_keep = conflicting_schools.order_by('-id').first()

                if not school_to_keep:
                    continue

                self.stdout.write(f"  -> ✅ Үлдээж байна: '{school_to_keep}' (ID: {school_to_keep.id})")

                schools_to_delete = conflicting_schools.exclude(id=school_to_keep.id)

                if schools_to_delete.exists():
                    for school in schools_to_delete:
                        self.stdout.write(self.style.WARNING(f"  -> 🔴 УСТГАЖ БАЙНА: '{school}' (ID: {school.id})"))

                    deleted_count, _ = schools_to_delete.delete()
                    total_deleted += deleted_count

            except Group.DoesNotExist:
                 self.stdout.write(self.style.ERROR(f"\n- ID {group_id} бүхий бүлэг олдсонгүй."))

        self.stdout.write(self.style.SUCCESS(f"\n--- ДҮН ---"))
        self.stdout.write(self.style.SUCCESS(
            f"Амжилттай: Нийт {total_deleted} сургуулийн илүүдэл бичлэгийг устгалаа."
        ))
        self.stdout.write(self.style.SUCCESS(
            "Одоо 'python manage.py migrate' коммандыг ажиллуулж болно."
        ))