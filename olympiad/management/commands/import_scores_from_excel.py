# management/commands/import_scores_from_excel.py

import pandas as pd
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.models import User
from olympiad.models import Olympiad, Problem, Result
from schools.models import School

class Command(BaseCommand):
    help = 'Заасан хавтас доторх бүх Excel файлаас олимпиадын оноог импортолно.'

    def add_arguments(self, parser):
        parser.add_argument('--directory', type=str, required=True, help='Импортлох Excel файлууд байрлах хавтасны зам')
        # --- ӨӨРЧЛӨЛТ 1: --force-import флаг нэмэх ---
        parser.add_argument(
            '--force-import',
            action='store_true',
            help='Сургуулийн группт харьяалагддаг эсэхийг шалгалгүйгээр оноог шууд импортлох.'
        )

    def handle(self, *args, **options):
        directory_path = options['directory']
        force_import = options['force_import'] # Флагийн утгыг авах

        if not os.path.isdir(directory_path):
            raise CommandError(f"Хавтас олдсонгүй: {directory_path}")

        processed_dir_path = os.path.join(directory_path, 'processed_scores')
        os.makedirs(processed_dir_path, exist_ok=True)

        self.stdout.write(self.style.NOTICE(f"'{directory_path}' хавтас доторх файлуудыг шалгаж байна..."))

        # --- ӨӨРЧЛӨЛТ 2: Флаг ашиглагдсан бол анхааруулга хэвлэх ---
        if force_import:
            self.stdout.write(self.style.WARNING("Анхаар! --force-import флаг ашиглагдсан тул сурагчийн сургуульд харьяалагдах болон нэрний зөрүүг шалгахгүй."))

        for filename in os.listdir(directory_path):
            if not filename.endswith(('.xlsx', '.xls')):
                continue

            file_path = os.path.join(directory_path, filename)
            self.stdout.write(f"\n--- '{filename}' файлыг боловсруулж байна ---")

            try:
                df_info = pd.read_excel(file_path, sheet_name='Мэдээлэл')
                info_dict = pd.Series(df_info.Утга.values,index=df_info.Түлхүүр).to_dict()
                olympiad_id = int(info_dict['olympiad_id'])
                school_id = int(info_dict['school_id'])
                self.stdout.write(f"\n Сургуулийн id: {school_id}")

                olympiad = Olympiad.objects.get(pk=olympiad_id)

                if force_import:
                    school = School.objects.all().first()
                else:
                    school = School.objects.get(pk=school_id)

                if not school.group:
                    self.stdout.write(self.style.ERROR(f"Алдаа: '{school.name}' сургуульд групп оноогоогүй тул файлыг алгасаж байна."))
                    continue

                df = pd.read_excel(file_path, sheet_name='Оноо')
                problems_map = {problem.order: problem for problem in Problem.objects.filter(olympiad=olympiad)}

                if 'ID' not in df.columns:
                    self.stdout.write(self.style.ERROR("Алдаа: 'Оноо' sheet-д 'ID' багана олдсонгүй. Файлыг алгасаж байна."))
                    continue

                updated_count, created_count, skipped_rows, invalid_scores = 0, 0, 0, 0

                for index, row in df.iterrows():
                    user_id = row.get('ID')
                    if pd.isna(user_id):
                        skipped_rows += 1
                        continue

                    try:
                        user = User.objects.get(pk=int(user_id))
                    except (User.DoesNotExist, ValueError, TypeError):
                        skipped_rows += 1
                        continue

                    # --- ӨӨРЧЛӨЛТ 3: Шалгалтыг --force-import үед алгасах ---
                    # Хэрэв force_import хийгээгүй бол л шалгалтыг ажиллуулна
                    if not force_import:
                        if not user.groups.filter(pk=school.group.id).exists() or \
                           user.last_name != str(row.get('Овог', '')) or \
                           user.first_name != str(row.get('Нэр', '')):
                            self.stdout.write(self.style.WARNING(f"  Мөр {index + 2}: ID={user_id} хэрэглэгчийн мэдээлэл зөрүүтэй эсвэл сургуульд харьяалагддаггүй. Алгасаж байна."))
                            skipped_rows += 1
                            continue

                    with transaction.atomic():
                        for order, problem in problems_map.items():
                            column_name = f'№{order}'
                            if column_name in df.columns:
                                score_value = row[column_name]
                                if pd.notna(score_value) and str(score_value).strip() != '':
                                    try:
                                        submitted_score = float(score_value)
                                        if submitted_score < 0:
                                            raise ValueError("Сөрөг оноог зөвшөөрөхгүй")

                                        obj, created = Result.objects.update_or_create(
                                            contestant=user, olympiad=olympiad, problem=problem,
                                            defaults={'score': submitted_score}
                                        )
                                        if created: created_count += 1
                                        else: updated_count += 1

                                    except (ValueError, TypeError):
                                        self.stdout.write(self.style.WARNING(f"    - {user.first_name}, {column_name}: Оноо '{score_value}' буруу форматтай тул алгаслаа."))
                                        invalid_scores += 1

                self.stdout.write(self.style.SUCCESS(
                    f"'{filename}' файл амжилттай боловсруулагдлаа. "
                    f"Үүссэн: {created_count}, Шинэчлэгдсэн: {updated_count}, "
                    f"Буруу оноотой: {invalid_scores}, Алгассан мөр: {skipped_rows}."
                ))

                processed_file_path = os.path.join(processed_dir_path, filename)
                os.rename(file_path, processed_file_path)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"'{filename}' файлыг боловсруулахад ноцтой алдаа гарлаа: {e}"))

        self.stdout.write(self.style.SUCCESS("\n--- Бүх файлуудыг шалгаж дууслаа. ---"))