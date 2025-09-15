import pandas as pd
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.models import User
from olympiad.models import Olympiad, Problem, Result
from schools.models import School

class Command(BaseCommand):
    help = 'Заасан хавтас доторх бүх Excel файлаас олимпиадын хариултыг импортолно.'

    def add_arguments(self, parser):
        parser.add_argument('--directory', type=str, required=True, help='Импортлох Excel файлууд байрлах хавтасны зам')

    def handle(self, *args, **options):
        directory_path = options['directory']

        if not os.path.isdir(directory_path):
            raise CommandError(f"Хавтас олдсонгүй: {directory_path}")

        # Боловсруулсан файлуудыг зөөх хавтас
        processed_dir_path = os.path.join(directory_path, 'processed')
        os.makedirs(processed_dir_path, exist_ok=True)

        self.stdout.write(self.style.NOTICE(f"'{directory_path}' хавтас доторх файлуудыг шалгаж байна..."))

        for filename in os.listdir(directory_path):
            if not filename.endswith(('.xlsx', '.xls')):
                continue

            file_path = os.path.join(directory_path, filename)
            self.stdout.write(f"\n--- '{filename}' файлыг боловсруулж байна ---")

            try:
                # --- Info Sheet-г уншиж, шалгах ---
                df_info = pd.read_excel(file_path, sheet_name='Мэдээлэл')
                info_dict = pd.Series(df_info.Утга.values,index=df_info.Түлхүүр).to_dict()
                olympiad_id = int(info_dict['olympiad_id'])
                school_id = int(info_dict['school_id'])

                olympiad = Olympiad.objects.get(pk=olympiad_id)
                school = School.objects.get(pk=school_id)

                if not school.group:
                    self.stdout.write(self.style.ERROR(f"Алдаа: '{school.name}' сургуульд групп оноогоогүй тул файлыг алгасаж байна."))
                    continue

                # --- Хариултын Sheet-г унших ---
                df = pd.read_excel(file_path, sheet_name='Хариулт')
                problems_map = {problem.order: problem for problem in Problem.objects.filter(olympiad=olympiad)}

                if 'ID' not in df.columns:
                    self.stdout.write(self.style.ERROR("Алдаа: 'Хариулт' sheet-д 'ID' багана олдсонгүй. Файлыг алгасаж байна."))
                    continue

                updated_count = 0
                created_count = 0
                skipped_rows = 0

                # --- Мөр бүрийг боловсруулах ---
                for index, row in df.iterrows():
                    user_id = row.get('ID')
                    if pd.isna(user_id):
                        self.stdout.write(self.style.WARNING(f"  Мөр {index + 2}: ID хоосон байна. Алгасаж байна."))
                        skipped_rows += 1
                        continue

                    try:
                        user = User.objects.get(pk=int(user_id))
                    except (User.DoesNotExist, ValueError, TypeError):
                        self.stdout.write(self.style.WARNING(f"  Мөр {index + 2}: ID={user_id} буруу эсвэл олдсонгүй. Алгасаж байна."))
                        skipped_rows += 1
                        continue

                    # ШАЛГАЛТ 1: СУРАГЧ ТУХАЙН СУРГУУЛЬД ХАРЬЯАЛАГДДАГ ЭСЭХ
                    if not user.groups.filter(pk=school.group.id).exists():
                        self.stdout.write(self.style.WARNING(f"  Мөр {index + 2}: ID={user_id} ({user.first_name}) хэрэглэгч '{school.name}' сургуульд харьяалагддаггүй. Алгасаж байна."))
                        skipped_rows += 1
                        continue

                    # ШАЛГАЛТ 2: НЭР ОВОГ ЗӨРҮҮТЭЙ ЭСЭХ
                    last_name_from_file = str(row.get('Овог', ''))
                    first_name_from_file = str(row.get('Нэр', ''))
                    if user.last_name != last_name_from_file or user.first_name != first_name_from_file:
                        self.stdout.write(self.style.WARNING(f"  Мөр {index + 2}: ID={user_id} хэрэглэгчийн нэр зөрүүтэй байна. Алгасаж байна."))
                        skipped_rows += 1
                        continue

                    with transaction.atomic():
                        for order, problem in problems_map.items():
                            column_name = f'№{order}'
                            if column_name in df.columns:
                                answer = row[column_name]
                                if pd.notna(answer) and str(answer).strip() != '':
                                    # ШАЛГАЛТ 3: НАТУРАЛ ТОО МӨН ЭСЭХ
                                    try:
                                        submitted_answer = int(float(answer))
                                        if submitted_answer <= 0:
                                            raise ValueError("Эерэг тоо биш")

                                        obj, created = Result.objects.update_or_create(
                                            contestant=user, olympiad=olympiad, problem=problem,
                                            defaults={'answer': submitted_answer}
                                        )
                                        if created: created_count += 1
                                        else: updated_count += 1

                                    except (ValueError, TypeError):
                                        self.stdout.write(self.style.WARNING(f"    - {user.first_name}, {column_name}: Хариулт '{answer}' натурал тоо биш тул алгаслаа."))

                self.stdout.write(self.style.SUCCESS(
                    f"'{filename}' файл амжилттай боловсруулагдлаа. Үүссэн: {created_count}, Шинэчлэгдсэн: {updated_count}, Алгассан: {skipped_rows}."
                ))

                # Амжилттай боловсруулсан файлыг зөөх
                processed_file_path = os.path.join(processed_dir_path, filename)
                os.rename(file_path, processed_file_path)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"'{filename}' файлыг боловсруулахад ноцтой алдаа гарлаа: {e}"))

        self.stdout.write(self.style.SUCCESS("\n--- Бүх файлуудыг шалгаж дууслаа. ---"))