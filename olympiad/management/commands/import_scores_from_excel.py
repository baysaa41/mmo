# management/commands/import_scores_from_excel.py

import pandas as pd
import os
import re
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.models import User, Group
from olympiad.models import Olympiad, Problem, Result, ScoreSheet
from schools.models import School
from accounts.models import UserMeta, Province, Grade, Level

class Command(BaseCommand):
    help = 'Заасан хавтас доторх бүх Excel файлаас олимпиадын оноог импортолно.'

    def add_arguments(self, parser):
        parser.add_argument('--directory', type=str, required=True, help='Импортлох Excel файлууд байрлах хавтасны зам')
        parser.add_argument(
            '--force-import',
            action='store_true',
            help='Сургуулийн группт харьяалагддаг эсэхийг шалгалгүйгээр оноог шууд импортлох.'
        )

    def extract_grade_number(self, grade_str):
        """7а, 7б гэх мэтээс 7 гэсэн дугаарыг гаргаж авна"""
        if pd.isna(grade_str):
            return None
        match = re.match(r'(\d+)', str(grade_str))
        if match:
            return int(match.group(1))
        return None

    def get_or_create_busad_school(self, province):
        """Тухайн дүүргийн 'Бусад' сургууль олох эсвэл үүсгэх"""
        school, created = School.objects.get_or_create(
            name=f"{province.name} - Бусад",
            province=province,
            defaults={'official_level_1': False, 'official_level_2': False}
        )
        if created:
            self.stdout.write(self.style.WARNING(f"  'Бусад' сургууль үүслээ: {school.name} (ID: {school.id})"))
        return school

    def find_matching_user(self, row, olympiad, province, sheet_name):
        """
        Овог нэрээр тохирох хэрэглэгч хайх.
        Дараах шалгалтуудыг хийнэ:
        1. Province дотор овог нэрээр хайх
        2. Level таарч байгаа эсэхийг шалгах
        3. Сургууль таарч байгаа эсэхийг шалгах (хэрэв өгөгдөлд байвал)
        4. Анги таарч байгаа эсэхийг шалгах (хэрэв өгөгдөлд байвал)
        5. Олон сурагч байвал round 1-д орсон эсэхийг шалгаад эхнийг сонгох
        """
        last_name = str(row.get('Овог', '')).strip()
        first_name = str(row.get('Нэр', '')).strip()

        if not last_name or not first_name:
            return None

        # Province дотор овог нэрээр хайх
        candidates = User.objects.filter(
            last_name=last_name,
            first_name=first_name,
            usermeta__province=province
        ).select_related('usermeta', 'usermeta__level', 'usermeta__grade', 'usermeta__school')

        if not candidates.exists():
            return None

        self.stdout.write(f"  {last_name} {first_name} нэртэй {candidates.count()} сурагч province-д олдлоо")

        # Level шалгалт
        olympiad_level = olympiad.level
        candidates = [u for u in candidates if u.usermeta and u.usermeta.level == olympiad_level]

        if not candidates:
            self.stdout.write(f"  Level {olympiad_level.name} таарахгүй байна")
            return None

        self.stdout.write(f"  Level таарсан: {len(candidates)} сурагч")

        # Сургууль шалгалт (хэрэв өгөгдөлд байвал)
        if 'Сургууль' in row.index and pd.notna(row.get('Сургууль')):
            school_name = str(row.get('Сургууль')).strip()
            candidates = [u for u in candidates if u.usermeta.school and school_name in u.usermeta.school.name]

            if not candidates:
                self.stdout.write(f"  Сургууль '{school_name}' таарахгүй байна")
                return None

            self.stdout.write(f"  Сургууль таарсан: {len(candidates)} сурагч")

        # Анги шалгалт (хэрэв өгөгдөлд байвал, S/T багш нарын ангиллын хувьд алгасах)
        if 'Анги' in row.index and pd.notna(row.get('Анги')):
            # S, T ангилал нь багш нарын ангилал тул анги шалгахгүй
            if not (olympiad_level.name.startswith('S') or olympiad_level.name.startswith('T')):
                grade_num = self.extract_grade_number(row.get('Анги'))
                if grade_num:
                    candidates = [u for u in candidates if u.usermeta.grade and u.usermeta.grade.id == grade_num]

                    if not candidates:
                        self.stdout.write(f"  Анги таарахгүй байна")
                        return None

                    self.stdout.write(f"  Анги таарсан: {len(candidates)} сурагч")

        # Олон сурагч байвал round 1 шалгалт
        if len(candidates) > 1:
            # Round 1-д орсон эсэхийг шалгах
            round1_candidates = []
            for user in candidates:
                # ScoreSheet эсвэл Result-ээр round 1 олимпиадад орсон эсэхийг шалгах
                participated_in_round1 = Result.objects.filter(
                    contestant=user,
                    olympiad__round=1
                ).exists() or ScoreSheet.objects.filter(
                    user=user,
                    olympiad__round=1
                ).exists()

                if participated_in_round1:
                    round1_candidates.append(user)

            if round1_candidates:
                self.stdout.write(f"  Round 1-д орсон {len(round1_candidates)} сурагч байна, эхнийг сонгоно")
                return round1_candidates[0]
            else:
                self.stdout.write(f"  Round 1-д орсон сурагч байхгүй, эхнийг сонгоно")
                return candidates[0]

        # 1 л сурагч байвал шууд буцаана
        if len(candidates) == 1:
            self.stdout.write(f"  1 сурагч олдлоо: ID={candidates[0].id}")
            return candidates[0]

        return None

    def create_user(self, row, olympiad, province, sheet_name):
        """Шинэ хэрэглэгч үүсгэх"""
        last_name = str(row.get('Овог', '')).strip()
        first_name = str(row.get('Нэр', '')).strip()

        if not last_name or not first_name:
            self.stdout.write(self.style.ERROR(f"  Овог нэр хоосон байна, сурагч үүсгэх боломжгүй"))
            return None

        # Username үүсгэх (u + timestamp эсвэл дараалал дугаар)
        latest_user = User.objects.order_by('-id').first()
        next_id = (latest_user.id + 1) if latest_user else 1
        username = f"u{next_id}"

        # Email
        email = 'auto-user@mmo.mn'

        # Province (эх файлын province)
        user_province = province

        # Level (sheet-ийн олимпиадын level)
        level = olympiad.level

        # Grade (өгөгдөлд байвал, байхгүй бол level-ийн дээд анги)
        # S, T ангилал нь багш нарын ангилал тул Excel-ээс анги уншихгүй
        grade = None
        if 'Анги' in row.index and pd.notna(row.get('Анги')):
            # Багш нарын ангиллын хувьд Excel-ээс анги уншихгүй
            if not (level.name.startswith('S') or level.name.startswith('T')):
                grade_num = self.extract_grade_number(row.get('Анги'))
                if grade_num:
                    try:
                        grade = Grade.objects.get(id=grade_num)
                    except Grade.DoesNotExist:
                        pass

        # Хэрэв grade олдоогүй бол level-ийн дээд анги
        if not grade:
            # Level name-ээс анги тодорхойлох: "D (7-8)" -> 8
            if level.name.startswith('B'):
                grade = Grade.objects.get(id=4)  # 4-р анги
            elif level.name.startswith('C'):
                grade = Grade.objects.get(id=6)  # 6-р анги
            elif level.name.startswith('D'):
                grade = Grade.objects.get(id=8)  # 8-р анги
            elif level.name.startswith('E'):
                grade = Grade.objects.get(id=10)  # 10-р анги
            elif level.name.startswith('F'):
                grade = Grade.objects.get(id=12)  # 12-р анги
            elif level.name.startswith('S') or level.name.startswith('T'):
                grade = Grade.objects.get(id=14)  # Багш
            else:
                grade = Grade.objects.get(id=12)  # Default

        # School (өгөгдөлд байвал хайна, байхгүй бол "Бусад")
        school = None
        if 'Сургууль' in row.index and pd.notna(row.get('Сургууль')):
            school_name = str(row.get('Сургууль')).strip()
            try:
                school = School.objects.filter(name__icontains=school_name, province=user_province).first()
            except School.DoesNotExist:
                pass

        if not school:
            school = self.get_or_create_busad_school(user_province)

        # User үүсгэх
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name
            )

            # UserMeta үүсгэх
            UserMeta.objects.create(
                user=user,
                province=user_province,
                level=level,
                grade=grade,
                school=school
            )

            # Сургуулийн бүлэгт нэмэх
            if school and school.group:
                user.groups.add(school.group)

            self.stdout.write(self.style.SUCCESS(
                f"  ✓ ШИНЭ СУРАГЧ ҮҮСЛЭЭ: ID={user.id}, {last_name} {first_name}, "
                f"{school.name if school else 'Сургуульгүй'}, {grade.name}"
            ))

        return user

    def get_user_for_row(self, row, olympiad, province, sheet_name, force_import):
        """
        Мөр бүрийн хувьд хэрэглэгч олох эсвэл үүсгэх логик.

        1. ID-аар хайх
        2. ID байгаа боловч овог нэр таараагүй бол овог нэрээр province-д хайх
        3. ID байхгүй бол овог нэрээр province-д хайх
        4. Олдохгүй бол шинэ сурагч үүсгэх
        """
        user_id = row.get('ID')
        last_name = str(row.get('Овог', '')).strip()
        first_name = str(row.get('Нэр', '')).strip()

        # 1. ID байгаа эсэхийг шалгах
        if pd.notna(user_id):
            try:
                user = User.objects.get(pk=int(user_id))

                # Овог нэр таарч байгаа эсэхийг шалгах
                if user.last_name == last_name and user.first_name == first_name:
                    # Force import эсвэл group шалгалт
                    if force_import or user.groups.exists():
                        self.stdout.write(f"  ✓ ID={user_id} олдлоо: {user.last_name} {user.first_name}")
                        return user
                else:
                    self.stdout.write(self.style.WARNING(
                        f"  ! ID={user_id} олдсон боловч овог нэр таараагүй: "
                        f"DB({user.last_name} {user.first_name}) vs Excel({last_name} {first_name})"
                    ))
                    # Овог нэрээр province-д хайх
                    matched_user = self.find_matching_user(row, olympiad, province, sheet_name)
                    if matched_user:
                        self.stdout.write(self.style.SUCCESS(f"  ✓ Овог нэрээр олдлоо: ID={matched_user.id}"))
                        return matched_user
                    else:
                        # Шинэ сурагч үүсгэх
                        return self.create_user(row, olympiad, province, sheet_name)

            except (User.DoesNotExist, ValueError, TypeError):
                self.stdout.write(self.style.WARNING(f"  ! ID={user_id} дата базд олдсонгүй"))
                # Овог нэрээр province-д хайх
                matched_user = self.find_matching_user(row, olympiad, province, sheet_name)
                if matched_user:
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Овог нэрээр олдлоо: ID={matched_user.id}"))
                    return matched_user
                else:
                    # Шинэ сурагч үүсгэх
                    return self.create_user(row, olympiad, province, sheet_name)
        else:
            # ID байхгүй - овог нэрээр province-д хайх
            self.stdout.write(f"  ID байхгүй, овог нэрээр хайж байна...")
            matched_user = self.find_matching_user(row, olympiad, province, sheet_name)
            if matched_user:
                self.stdout.write(self.style.SUCCESS(f"  ✓ Овог нэрээр олдлоо: ID={matched_user.id}"))
                return matched_user
            else:
                # Шинэ сурагч үүсгэх
                return self.create_user(row, olympiad, province, sheet_name)

        return None

    def handle(self, *args, **options):
        directory_path = options['directory']
        force_import = options['force_import']

        if not os.path.isdir(directory_path):
            raise CommandError(f"Хавтас олдсонгүй: {directory_path}")

        processed_dir_path = os.path.join(directory_path, 'processed_scores')
        os.makedirs(processed_dir_path, exist_ok=True)

        self.stdout.write(self.style.NOTICE(f"'{directory_path}' хавтас доторх файлуудыг шалгаж байна..."))

        if force_import:
            self.stdout.write(self.style.WARNING("Анхаар! --force-import флаг ашиглагдсан."))

        # Нийт статистик
        total_created_users = 0
        total_matched_users = 0

        for filename in os.listdir(directory_path):
            if not filename.endswith(('.xlsx', '.xls')):
                continue

            file_path = os.path.join(directory_path, filename)
            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(f"'{filename}' файлыг боловсруулж байна")
            self.stdout.write(f"{'='*80}")

            try:
                # Мэдээлэл sheet уншиж олимпиад, province олох
                excel_file = pd.ExcelFile(file_path)

                # Check for Мэдээлэл sheet
                if 'Мэдээлэл' not in excel_file.sheet_names:
                    self.stdout.write(self.style.ERROR("Алдаа: 'Мэдээлэл' sheet олдсонгүй. Файлыг алгасаж байна."))
                    continue

                df_info = pd.read_excel(file_path, sheet_name='Мэдээлэл')

                # Parse metadata - flexible structure
                olympiad = None
                province = None

                for idx, row in df_info.iterrows():
                    if len(row) >= 2:
                        key = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
                        value = row.iloc[1]

                        if 'olympiad' in key.lower() and 'id' in key.lower():
                            try:
                                olympiad = Olympiad.objects.get(pk=int(value))
                                self.stdout.write(f"Олимпиад: {olympiad.name} (ID: {olympiad.id}, Level: {olympiad.level.name})")
                            except (Olympiad.DoesNotExist, ValueError):
                                self.stdout.write(self.style.ERROR(f"Олимпиад ID={value} олдсонгүй"))
                                continue

                        if 'аймаг' in key.lower() or 'province' in key.lower():
                            if 'id' in key.lower() and pd.notna(value):
                                try:
                                    province = Province.objects.get(pk=int(value))
                                    self.stdout.write(f"Аймаг/Дүүрэг: {province.name} (ID: {province.id})")
                                except (Province.DoesNotExist, ValueError):
                                    pass
                            elif 'нэр' in key.lower() and pd.notna(value):
                                province_name = str(value).strip()
                                province = Province.objects.filter(name__icontains=province_name).first()
                                if province:
                                    self.stdout.write(f"Аймаг/Дүүрэг: {province.name} (ID: {province.id})")

                if not olympiad:
                    self.stdout.write(self.style.ERROR("Алдаа: Олимпиадын мэдээлэл олдсонгүй. Файлыг алгасаж байна."))
                    continue

                if not province:
                    self.stdout.write(self.style.ERROR("Алдаа: Аймгийн мэдээлэл олдсонгүй. Файлыг алгасаж байна."))
                    continue

                # Process all sheets with scores
                problems_map = {problem.order: problem for problem in Problem.objects.filter(olympiad=olympiad)}

                updated_count, created_count, skipped_rows, invalid_scores = 0, 0, 0, 0
                created_users_count = 0
                matched_users_count = 0

                for sheet_name in excel_file.sheet_names:
                    if sheet_name == 'Мэдээлэл':
                        continue

                    self.stdout.write(f"\n--- Sheet: '{sheet_name}' ---")

                    df = pd.read_excel(file_path, sheet_name=sheet_name)

                    if 'ID' not in df.columns and 'Овог' not in df.columns:
                        self.stdout.write(self.style.WARNING(f"  'ID' эсвэл 'Овог' багана олдсонгүй, алгасаж байна."))
                        continue

                    for index, row in df.iterrows():
                        # Skip empty rows
                        if pd.isna(row.get('Овог')) and pd.isna(row.get('Нэр')):
                            continue

                        self.stdout.write(f"\nМөр {index + 2}: {row.get('Овог')} {row.get('Нэр')} (Excel ID: {row.get('ID')})")

                        # Get or create user
                        user = self.get_user_for_row(row, olympiad, province, sheet_name, force_import)

                        if not user:
                            self.stdout.write(self.style.ERROR(f"  Хэрэглэгч олдсонгүй эсвэл үүсгэж чадсангүй"))
                            skipped_rows += 1
                            continue

                        # Track statistics
                        if user.id and user.date_joined.date() == user.last_login.date() if user.last_login else False:
                            created_users_count += 1
                        else:
                            matched_users_count += 1

                        # Import scores
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
                                            if created:
                                                created_count += 1
                                            else:
                                                updated_count += 1

                                        except (ValueError, TypeError):
                                            self.stdout.write(self.style.WARNING(f"    - {column_name}: Оноо '{score_value}' буруу форматтай"))
                                            invalid_scores += 1

                self.stdout.write(self.style.SUCCESS(
                    f"\n'{filename}' файл амжилттай боловсруулагдлаа.\n"
                    f"  Үүссэн оноо: {created_count}, Шинэчлэгдсэн: {updated_count}\n"
                    f"  Шинэ сурагч: {created_users_count}, Олдсон сурагч: {matched_users_count}\n"
                    f"  Буруу оноо: {invalid_scores}, Алгассан мөр: {skipped_rows}"
                ))

                total_created_users += created_users_count
                total_matched_users += matched_users_count

                processed_file_path = os.path.join(processed_dir_path, filename)
                os.rename(file_path, processed_file_path)

            except Exception as e:
                import traceback
                self.stdout.write(self.style.ERROR(f"'{filename}' файлыг боловсруулахад алдаа гарлаа: {e}"))
                self.stdout.write(traceback.format_exc())

        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*80}\n"
            f"ЭЦСИЙН ТАЙЛАН\n"
            f"{'='*80}\n"
            f"Нийт шинэ сурагч үүсгэсэн: {total_created_users}\n"
            f"Нийт олдсон сурагч: {total_matched_users}\n"
            f"{'='*80}"
        ))
