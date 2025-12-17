# your_app/management/commands/show_school_staff.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

# Таны models.py файлд "schools.School" гэж заасан тул
# School загварыг "schools" апп-аас импорт хийж байна.
# Хэрэв өөр апп-д байвал 'schools' гэснийг солиорой.
from schools.models import School

class Command(BaseCommand):
    help = 'Lists all staff members (excluding self) from the schools managed by a specific user.'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='The username of the school moderator.')

    def handle(self, *args, **options):
        username = options['username']

        # 1. Удирдагч багшийг олох
        try:
            manager = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Хэрэглэгч '{username}' олдсонгүй."))
            return

        # 2. Тухайн багшийн удирддаг сургуулиудыг 'moderating' (related_name)-р олох
        moderated_schools = manager.moderating.all().select_related('group')

        if not moderated_schools.exists():
            self.stdout.write(self.style.WARNING(f"Хэрэглэгч '{username}' ямар нэг сургууль удирддаггүй."))
            return

        self.stdout.write(self.style.SUCCESS(f"'{manager.username}' багшийн удирддаг сургуулиудын ажилтнууд:"))

        # 3. Сургууль тус бүрээр давтах
        for school in moderated_schools:
            self.stdout.write(self.style.SUCCESS(f"\n--- Сургууль: {school.name} ---"))

            # 4. Сургууль нь групп-тэй холбогдсон эсэхийг шалгах
            if not school.group:
                self.stdout.write(self.style.NOTICE(f"  (Энэ сургууль системд групп-тэй холбогдоогүй байна)"))
                continue

            # 5. Групп-д хамаарах бусад хэрэглэгчдийг олох (менежерийг өөрийг нь хасах)
            #    .select_related('data') нь UserMeta-г (утас) авахад хэрэглэгдэнэ
            staff_list = school.group.user_set.exclude(id=manager.id).select_related('data')

            if not staff_list.exists():
                self.stdout.write(f"  (Энэ сургуулийн групп-д өөр багш бүртгэлгүй байна)")
                continue

            # 6. Олдсон багш нарын жагсаалтыг хэвлэх
            for staff in staff_list:
                mobile = "Утасгүй"
                # UserMeta (data) холбоосоос утас авах
                if hasattr(staff, 'data') and staff.data and staff.data.mobile:
                    mobile = staff.data.mobile

                self.stdout.write(
                    f"  - {staff.last_name}, {staff.first_name} "
                    f"(Username: {staff.username}, Утас: {mobile})"
                )