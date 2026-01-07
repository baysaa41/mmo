from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction


class Command(BaseCommand):
    help = 'auto-user@mmo.mn email-тэй хэрэглэгчдийг бүх холбоотой мэдээллийн хамт устгана'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Устгахгүйгээр зөвхөн тайлан харуулна'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Баталгаажуулалтын асуулт алгасна'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        confirm = options['confirm']

        # auto-user@mmo.mn email-тэй хэрэглэгчдийг олох
        auto_users = User.objects.filter(email='auto-user@mmo.mn')
        user_count = auto_users.count()

        if user_count == 0:
            self.stdout.write(self.style.SUCCESS('auto-user@mmo.mn email-тэй хэрэглэгч олдсонгүй.'))
            return

        self.stdout.write(self.style.WARNING(f'\n{user_count} хэрэглэгч олдлоо:\n'))

        # Дэлгэрэнгүй мэдээлэл харуулах
        for user in auto_users:
            self.stdout.write(f'  ID: {user.id}')
            self.stdout.write(f'  Нэр: {user.last_name} {user.first_name}')
            self.stdout.write(f'  Username: {user.username}')
            self.stdout.write(f'  Email: {user.email}')

            # Холбоотой мэдээллүүдийг тоолох
            try:
                usermeta = user.data
                self.stdout.write(f'  Сургууль: {usermeta.school if hasattr(usermeta, "school") else "Байхгүй"}')
                self.stdout.write(f'  Анги: {usermeta.grade if hasattr(usermeta, "grade") else "Байхгүй"}')
            except:
                self.stdout.write(f'  UserMeta: Байхгүй')

            # Олимпиадын дүн
            result_count = user.contest_results.count()
            scoresheet_count = user.results.count()
            self.stdout.write(f'  Олимпиадын дүн (Result): {result_count}')
            self.stdout.write(f'  Олимпиадын дүн (ScoreSheet): {scoresheet_count}')

            # Багш-сурагчийн холбоо
            teacher_count = user.students.count()
            student_count = user.teachers.count()
            if teacher_count > 0:
                self.stdout.write(f'  Багшаар: {teacher_count} сурагчтай')
            if student_count > 0:
                self.stdout.write(f'  Сурагчаар: {student_count} багштай')

            # Файл оруулсан эсэх
            uploaded_files = user.uploadedfile_set.count()
            if uploaded_files > 0:
                self.stdout.write(f'  Файл: {uploaded_files}')

            self.stdout.write('  ' + '-' * 50)

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'\n--dry-run горим: {user_count} хэрэглэгч устгагдахгүй байна.'))
            self.stdout.write('\nУстгагдах мэдээлэл:')
            self.stdout.write('  - UserMeta (хэрэглэгчийн нэмэлт мэдээлэл)')
            self.stdout.write('  - Result (олимпиадын дүн)')
            self.stdout.write('  - ScoreSheet (оноо хуудас)')
            self.stdout.write('  - TeacherStudent (багш-сурагчийн холбоо)')
            self.stdout.write('  - UploadedFile (оруулсан файлууд)')
            self.stdout.write('  - Author (зохиогчийн мэдээлэл)')
            self.stdout.write('  - Бусад CASCADE холбоотой мэдээлэл')
            return

        if not confirm:
            self.stdout.write(self.style.WARNING(
                f'\n⚠️  АНХААР: Энэ үйлдэл {user_count} хэрэглэгч болон '
                'тэдний БҮХ холбоотой мэдээллийг ЭРГҮҮЛЭХ БОЛОМЖГҮЙ устгана!'
            ))
            confirmation = input(f'\nҮргэлжлүүлэх үү? Баталгаажуулахын тулд "USTGAH" гэж бичнэ үү: ')
            if confirmation != 'USTGAH':
                self.stdout.write(self.style.ERROR('Цуцлагдсан.'))
                return

        # Устгах үйлдлийг гүйцэтгэх
        try:
            with transaction.atomic():
                # Устгахын өмнө статистик цуглуулах
                total_results = sum(u.contest_results.count() for u in auto_users)
                total_scoresheets = sum(u.results.count() for u in auto_users)

                deleted_count, deleted_details = auto_users.delete()

                self.stdout.write(self.style.SUCCESS(f'\n✓ Амжилттай устгалаа!'))
                self.stdout.write(f'Устгасан хэрэглэгч: {user_count}')
                self.stdout.write(f'Устгасан Result: {total_results}')
                self.stdout.write(f'Устгасан ScoreSheet: {total_scoresheets}')
                self.stdout.write(f'\nНийт устгасан объект: {deleted_count}')

                # Дэлгэрэнгүй
                if deleted_details:
                    self.stdout.write('\nУстгасан объектуудын дэлгэрэнгүй:')
                    for model, count in deleted_details.items():
                        if count > 0:
                            self.stdout.write(f'  {model}: {count}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Алдаа гарлаа: {str(e)}'))
            raise
