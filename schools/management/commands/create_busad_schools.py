from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from schools.models import School
from accounts.models import Province


class Command(BaseCommand):
    help = 'Province бүрд "Бусад" нэртэй сургууль үүсгэх'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Зөвхөн харах горим (өгөгдөл хадгалахгүй)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING("\n=== DRY RUN ГОРИМ ===\n"))
        else:
            self.stdout.write(self.style.SUCCESS("\n=== PRODUCTION ГОРИМ ===\n"))

        # Бүх province-уудыг авах
        provinces = Province.objects.all().order_by('id')

        if not provinces.exists():
            self.stdout.write(self.style.ERROR("❌ Province олдсонгүй!"))
            return

        self.stdout.write(self.style.SUCCESS(f"📍 Нийт {provinces.count()} province олдлоо\n"))

        created_count = 0
        existing_count = 0
        error_count = 0

        for province in provinces:
            school_name = "Бусад"

            # Тухайн province-д "Бусад" нэртэй сургууль байгаа эсэхийг шалгах
            existing_school = School.objects.filter(
                province=province,
                name=school_name
            ).first()

            if existing_school:
                self.stdout.write(
                    f"  ℹ️  {province.name}: '{school_name}' сургууль аль хэдийн байна (ID: {existing_school.id})"
                )
                existing_count += 1
                continue

            # Dry run бол зөвхөн мэдээлэл харуулах
            if dry_run:
                group_name = f"{province.name}_{school_name}"
                self.stdout.write(self.style.WARNING(
                    f"  🔍 {province.name}: '{school_name}' сургууль ба '{group_name}' auth_group үүсгэх шаардлагатай"
                ))
                created_count += 1
                continue

            # Шинэ сургууль үүсгэх
            try:
                # auth_group үүсгэх
                group_name = f"{province.name}_{school_name}"
                group, group_created = Group.objects.get_or_create(name=group_name)

                group_status = "шинэ group үүсгэгдлээ" if group_created else "group аль хэдийн байсан"

                # School үүсгэх
                school = School.objects.create(
                    name=school_name,
                    province=province,
                    group=group,
                    is_official_participation=False
                )

                self.stdout.write(self.style.SUCCESS(
                    f"  ✅ {province.name}: '{school_name}' сургууль үүсгэгдлээ (ID: {school.id}, Group: {group.name}, {group_status})"
                ))
                created_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"  ❌ {province.name}: Алдаа гарлаа - {e}"
                ))
                error_count += 1

        # Дүгнэлт
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS(f"\n📊 ДҮГНЭЛТ:"))
        self.stdout.write(f"  • Нийт province: {provinces.count()}")
        self.stdout.write(self.style.SUCCESS(f"  • Үүсгэсэн сургууль: {created_count}"))
        self.stdout.write(f"  • Аль хэдийн байсан: {existing_count}")
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"  • Алдаа гарсан: {error_count}"))
        self.stdout.write("")
