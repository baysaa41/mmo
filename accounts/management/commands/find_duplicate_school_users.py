from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db.models import Count

class Command(BaseCommand):
    help = 'Хоёр ба түүнээс дээш сургуульд харьяалагддаг хэрэглэгчдийг олж, жагсаалтыг харуулна.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Давхардсан сургуультай хэрэглэгчдийг хайж байна...'))

        # Сургуулийн групп (school.group_id_isnull=False)
        # доторх хэрэглэгчдийг группээр нь тоолох
        users_with_multiple_schools = User.objects.annotate(
            school_group_count=Count('groups__school')
        ).filter(
            school_group_count__gte=2
        )

        if not users_with_multiple_schools.exists():
            self.stdout.write(self.style.SUCCESS('Давхардсан сургуультай хэрэглэгч олдсонгүй.'))
            return

        self.stdout.write(self.style.WARNING(
            f'Нийт {users_with_multiple_schools.count()} хэрэглэгч 2 ба түүнээс дээш сургуульд бүртгэлтэй байна:'
        ))

        # Хэрэглэгч бүрийн мэдээллийг хэвлэх
        for user in users_with_multiple_schools:
            self.stdout.write(f"\n- Хэрэглэгч: {user.get_full_name()} (ID: {user.id}, Username: {user.username}, Утас: {user.data.mobile})")

            # Тухайн хэрэглэгчийн харьяалагддаг бүх сургуулийг олох
            schools = user.groups.filter(school__isnull=False).select_related('school')

            self.stdout.write("  Харьяалагдах сургуулиуд:")
            for group in schools:
                # group.school нь OneToOneField тул group-оос school-г шууд авах боломжтой
                self.stdout.write(f"    - {group.school.name} (Group: {group.name})")

        self.stdout.write(self.style.SUCCESS('\nШалгаж дууслаа.'))