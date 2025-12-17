from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import UserMeta # Таны сурагчийн мэдээлэл хадгалдаг модел

class Command(BaseCommand):
    help = 'Сурагчдын анги, ангиллыг шинэчилж, төгсөгчдийн үүргийг тохируулна.'

    def handle(self, *args, **options):
        # --- Тогтмол утгууд ---
        GRADUATING_GRADE_ID = 12
        NEW_GRADE_ID_FOR_GRADUATES = 17
        NEW_LEVEL_ID_FOR_GRADUATES = 8

        NEW_LEVEL_FOR_GRADE = {
            3: 1, 4: 1,
            5: 2, 6: 2,
            7: 3, 8: 3,
            9: 4, 10: 4,
            11: 5, 12: 5,
        }

        self.stdout.write('Анги дэвшүүлэх процесс эхэлж байна...')

        confirm = input('Та мэдээллийн сангийн нөөц (backup) хийсэн үү? Үргэлжлүүлэх үү? (yes/no): ')
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.WARNING('Үйлдэл цуцлагдлаа.'))
            return

        try:
            with transaction.atomic():
                total_advanced = 0

                # --- ЭНЭ ХЭСГИЙН ДАРААЛАЛ ӨӨРЧЛӨГДСӨН ---

                # 1. ЭХЛЭЭД 12-р ангийн сурагчдыг төгсгөх
                students_to_graduate = UserMeta.objects.filter(grade_id=GRADUATING_GRADE_ID)
                graduated_count = students_to_graduate.update(
                    grade_id=NEW_GRADE_ID_FOR_GRADUATES,
                    level_id=NEW_LEVEL_ID_FOR_GRADUATES
                )

                if graduated_count > 0:
                    self.stdout.write(
                        f'- {GRADUATING_GRADE_ID}-р ангийн {graduated_count} сурагчийг шинэчиллээ: '
                        f'grade_id={NEW_GRADE_ID_FOR_GRADUATES}, level_id={NEW_LEVEL_ID_FOR_GRADUATES}'
                    )

                # 2. ДАРАА НЬ бусад ангийг (11-ээс 1) ухрааж дэвшүүлэх
                for old_grade_id in range(11, 0, -1):
                    new_grade_id = old_grade_id + 1

                    new_level_id = NEW_LEVEL_FOR_GRADE.get(new_grade_id)
                    students_in_grade = UserMeta.objects.filter(grade_id=old_grade_id)

                    update_data = {'grade_id': new_grade_id}
                    if new_level_id:
                        update_data['level_id'] = new_level_id

                    updated_count = students_in_grade.update(**update_data)

                    if updated_count > 0:
                        self.stdout.write(
                            f'- {old_grade_id}-р ангийн {updated_count} сурагчийг {new_grade_id}-р анги болголоо.'
                        )
                        total_advanced += updated_count

                self.stdout.write(self.style.SUCCESS('--- ПРОЦЕСС АМЖИЛТТАЙ ДУУСЛАА ---'))
                self.stdout.write(f'Нийт {graduated_count} сурагч төгсөж, үүрэг нь шинэчлэгдлээ.')
                self.stdout.write(f'Нийт {total_advanced} сурагчийн анги дэвшлээ.')


        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Алдаа гарлаа: {e}'))