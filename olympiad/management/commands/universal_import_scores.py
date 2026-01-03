import os
import re
import pandas as pd
import numpy as np
from datetime import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from olympiad.models import Olympiad, Problem, Result
from accounts.models import Province, UserMeta
from schools.models import School
from rapidfuzz import fuzz
import unicodedata

User = get_user_model()

# Кирилл → Латин romanization map
CYRILLIC_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'j', 'з': 'z',
    'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'ө': 'o', 'п': 'p',
    'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ү': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch',
    'ш': 'sh', 'щ': 'sh', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo', 'Ж': 'J', 'З': 'Z',
    'И': 'I', 'Й': 'I', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O', 'Ө': 'O', 'П': 'P',
    'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U', 'Ү': 'U', 'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch',
    'Ш': 'Sh', 'Щ': 'Sh', 'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
}


class Command(BaseCommand):
    help = 'Оноо импортлох универсал тушаал - Excel/CSV файлуудаас оноог автоматаар импортлоно'

    """
    PROVINCE АВАХ ЛОГИК:
    ====================
    1. Эхлээд файлаас province_id-г хайна:
       - Хавтасны "Мэдээлэл" файлаас
       - Эсвэл файл бүрийн "Мэдээлэл" sheet-ээс

    2. Хэрэв файлаас олдохгүй бол эхний 3-5 хэрэглэгчийн province-ээс
       inference хийнэ (хамгийн олон гарсан province-ийг сонгоно)

    3. Province тогтсоны ДАРАА тухайн province дотроо сургууль хайна

    4. Шинэ хэрэглэгч үүсгэхдээ province-ийг зөвхөн файл/хэрэглэгчдээс
       авна, сургуулийн province-ээс АВАХГҮЙ

    СУРГУУЛЬ ХАЙХ ЛОГИК:
    ====================
    - Сургуулийн нэрийг normalize хийж (fuzzy matching ашиглана)
    - Эхлээд province дотроо хайна (similarity >= 70%)
    - Олдохгүй бол бүх сургуулиудаас хайна (similarity >= 70%)
    """

    def add_arguments(self, parser):
        parser.add_argument('config', type=str, help='Config (info.csv) файлын зам')
        parser.add_argument('data_path', type=str, help='Файлууд байрлах хавтас')
        parser.add_argument('--dry-run', action='store_true', help='Зөвхөн харах горим (өгөгдөл хадгалахгүй)')
        parser.add_argument('--log-file', type=str, default='import_log.txt', help='Log файлын нэр')
        parser.add_argument('--move-to-processed', action='store_true', help='Амжилттай импортолсон файлуудыг processed фолдерт хуулах')

    # Ангиллын pattern - sheet нэрээс ангилал таних
    CATEGORY_PATTERNS = {
        'C': r'([CС][\s\(\-]|[\s\(\-][CС][\s\)\-]|5-6|^[CС]$|5-р\s+анги|6-р\s+анги|-5$|-6$)',
        'D': r'(D[\s\(\-]|[\s\(\-]D[\s\)\-]|7-8|^D$|7-р\s+анги|8-р\s+анги|-7$|-8$)',
        'E': r'([EЕ][\s\(\-]|[\s\(\-][EЕ][\s\)\-]|9-10|^[EЕ]$|9-р\s+анги|10-р\s+анги|-9$|-10$)',
        'F': r'(F[\s\(\-]|[\s\(\-]F[\s\)\-]|11-12|^F$|11-р\s+анги|12-р\s+анги|-11$|-12$)',
        'S': r'(S[\s\(\-]|[\s\(\-][S][\s\)\-]|Бага\s+багш|Бага\s+анги|^S$)',
        'T': r'(T[\s\(\-]|[\s\(\-][T][\s\)\-]|Дунд\s+багш|Дунд\s+анги|^T$)',
    }

    def handle(self, *args, **options):
        config_path = options['config']
        data_path = options['data_path']
        dry_run = options['dry_run']
        log_file = options['log_file']

        # Статистик хадгалах
        self.stats = {
            'total_files': 0,
            'total_sheets': 0,
            'total_rows_processed': 0,
            'total_scores_saved': 0,
            'users_created': 0,  # Шинээр үүсгэсэн хэрэглэгчдийн тоо
            'province_updated': 0,  # Province шинэчилсэн хэрэглэгчид
            'users_not_found': [],
            'olympiad_errors': [],
            'missing_groups': [],  # Устсан группын мэдээлэл
            'processed_files': [],  # Амжилттай импортолсон файлууд
            'start_time': datetime.now(),
            'current_province_id': None,
            'current_province_name': None,
        }

        # Config унших
        try:
            config_df = pd.read_csv(config_path)
            config_map = dict(zip(config_df.iloc[:, 0].astype(str).str.strip(), config_df.iloc[:, 1]))
            self.stdout.write(self.style.SUCCESS(f"✅ Config файл уншигдлаа: {len(config_map)} ангилал"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Config файл уншихад алдаа: {e}"))
            return

        all_files = sorted([f for f in os.listdir(data_path) if f.endswith(('.xlsx', '.csv'))])
        self.stats['total_files'] = len([f for f in all_files if "Мэдээлэл" not in f])

        # 1. Мэдээлэл хайх
        file_province_id = None
        info_file = next((f for f in all_files if "Мэдээлэл" in f), None)
        if info_file:
            path = os.path.join(data_path, info_file)
            try:
                info_df = pd.read_excel(path) if path.endswith('.xlsx') else pd.read_csv(path)
                file_province_id = self.extract_province_id(info_df)
                if file_province_id:
                    province = Province.objects.filter(id=file_province_id).first()
                    province_name = province.name if province else "Тодорхойгүй"
                    self.stats['current_province_id'] = file_province_id
                    self.stats['current_province_name'] = province_name
                    self.stdout.write(self.style.SUCCESS(f"\n📍 АЙМАГ: {province_name} (ID: {file_province_id})"))
                else:
                    self.stdout.write(self.style.WARNING(f"\n⚠️ Аймгийн ID олдсонгүй - аймаг шалгалт хийхгүй"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"⚠️ Мэдээлэл файл уншихад алдаа: {e}"))

        # 2. Файлуудыг боловсруулах
        for filename in all_files:
            if "Мэдээлэл" in filename:
                continue

            filepath = os.path.join(data_path, filename)
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write(self.style.MIGRATE_HEADING(f"📄 ФАЙЛ: {filename}"))
            self.stdout.write("=" * 80)

            # Файл тус бүрээс province_id шалгах
            current_file_province_id = file_province_id  # Default - нийтлэг province_id
            file_processed_successfully = True  # Файл амжилттай боловсруулагдсан эсэх

            try:
                if filename.endswith('.xlsx'):
                    excel = pd.ExcelFile(filepath)

                    # Файл дотроос "Мэдээлэл" sheet хайх
                    info_sheets = [s for s in excel.sheet_names if "Мэдээлэл" in s or "МЭДЭЭЛЭЛ" in s]
                    if info_sheets:
                        try:
                            info_df = pd.read_excel(filepath, sheet_name=info_sheets[0])
                            file_specific_province = self.extract_province_id(info_df)
                            if file_specific_province:
                                current_file_province_id = file_specific_province
                                province = Province.objects.filter(id=file_specific_province).first()
                                province_name = province.name if province else "Тодорхойгүй"
                                self.stats['current_province_id'] = file_specific_province
                                self.stats['current_province_name'] = province_name
                                self.stdout.write(self.style.SUCCESS(f"📍 Файл аймаг: {province_name} (ID: {file_specific_province})"))
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f"⚠️ Файлын Мэдээлэл sheet уншихад алдаа: {e}"))

                    for sheet_name in excel.sheet_names:
                        if "Мэдээлэл" in sheet_name or "МЭДЭЭЛЭЛ" in sheet_name:
                            continue
                        df = pd.read_excel(filepath, sheet_name=sheet_name)
                        self.process_target(df, sheet_name, filename, config_map, current_file_province_id, dry_run)
                else:
                    df = pd.read_csv(filepath)
                    self.process_target(df, filename, filename, config_map, current_file_province_id, dry_run)

                # Файл амжилттай боловсруулагдсан
                if file_processed_successfully:
                    self.stats['processed_files'].append(filepath)

            except Exception as e:
                import traceback
                self.stdout.write(self.style.ERROR(f"❌ Файл боловсруулахад алдаа: {e}"))
                self.stdout.write(self.style.ERROR(f"   Traceback: {traceback.format_exc()}"))
                file_processed_successfully = False
                continue

        # 3. Эцсийн тайлан
        self.print_summary(dry_run)

        # 4. Log файл бичих
        if (self.stats['users_not_found'] or self.stats['olympiad_errors'] or
            self.stats['missing_groups']):
            self.write_log_file(log_file, dry_run)

        # 5. Файлуудыг processed фолдерт хуулах
        if options.get('move_to_processed') and not dry_run and self.stats['processed_files']:
            self.move_files_to_processed(data_path)

    def process_target(self, df, identifier, filename, config_map, province_id, dry_run):
        category = self.identify_category(identifier)
        self.stats['total_sheets'] += 1

        if category and category in config_map:
            olympiad_id = config_map[category]

            # Олимпиадыг шалгах
            try:
                olympiad = Olympiad.objects.get(id=olympiad_id)
                self.stdout.write(f"   🔹 Sheet: {identifier} → Олимпиад: {olympiad.name} (ID: {olympiad_id})")

                # Олимпиадын төлөв шалгах
                if not olympiad.is_grading:
                    self.stdout.write(self.style.WARNING(
                        f"      ⚠️ Анхааруулга: Олимпиад is_grading=False байна"
                    ))

            except Olympiad.DoesNotExist:
                error_info = {
                    'message': f"OLYMPIAD NOT FOUND: ID {olympiad_id} for category {category}",
                    'file': filename,
                    'sheet': identifier,
                    'province_id': province_id,
                    'province_name': self.stats.get('current_province_name', 'Тодорхойгүй')
                }
                self.stats['olympiad_errors'].append(error_info)
                self.stdout.write(self.style.ERROR(f"   ❌ {error_info['message']}"))
                return

            # Шинэ ухаалаг бүтэц таних систем ашиглах
            data_df, column_map = self.detect_data_structure(df, category)
            if data_df is not None and column_map is not None:
                # Province_id олдоогүй бол эхний сурагчдаас олох оролдоно
                if not province_id:
                    province_id = self.infer_province_from_data(data_df, column_map)

                count = self.process_rows_smart(data_df, column_map, olympiad_id,
                                               filename, identifier, province_id, dry_run, category)
                msg = f"   📊 Боловсруулсан: {count} мөр"
                self.stdout.write(self.style.SUCCESS(msg) if count > 0 else self.style.WARNING(msg))
            else:
                self.stdout.write(self.style.ERROR(f"   ❌ Дата бүтэц танигдсангүй!"))
        else:
            self.stdout.write(self.style.WARNING(f"   ⚠️ Ангилал танигдсангүй: {identifier}"))

    def process_rows_smart(self, df, column_map, olympiad_id, filename, source, province_id, dry_run, category=None):
        """
        Шинэ ухаалаг мөр боловсруулах систем - column_map ашиглах
        category: Sheet-ийн ангилал (C, D, E, F, S, T) - Grade/Level тодорхойлоход ашиглана
        """
        try:
            olympiad = Olympiad.objects.get(id=olympiad_id)
            problems = Problem.objects.filter(olympiad=olympiad).order_by('order')

            if not problems.exists():
                self.stdout.write(self.style.WARNING(f"      ⚠️ Олимпиадад асуулт байхгүй байна!"))
                return 0

        except Olympiad.DoesNotExist:
            return 0

        # column_map-аас хэрэгтэй мэдээллийг авах
        id_col = column_map['id_col']
        last_name_col = column_map['last_name_col']
        first_name_col = column_map['first_name_col']
        school_col = column_map.get('school_col', None)
        score_cols = column_map['score_cols']  # [(col_name, problem_number), ...]

        # Problem objects-ийг problem_number-аар зурагт хийх
        problem_map = {}
        for prob in problems:
            problem_map[prob.order] = prob

        # score_cols дахь problem_number-үүд олимпиадад байгаа эсэхийг шалгах
        valid_score_cols = []
        for col_name, prob_num in score_cols:
            if prob_num in problem_map:
                valid_score_cols.append((col_name, prob_num, problem_map[prob_num]))
            else:
                self.stdout.write(self.style.WARNING(
                    f"      ⚠️ Асуулт #{prob_num} олимпиадад байхгүй (багана: {col_name})"
                ))

        if not valid_score_cols:
            self.stdout.write(self.style.WARNING(f"      ⚠️ Хүчинтэй оноо багана олдсонгүй"))
            return 0

        # Мөр бүрийг боловсруулах
        row_count = 0
        scores_saved = 0
        total_rows = len(df)

        for idx, row in df.iterrows():
            # Progress
            if total_rows > 100 and (idx + 1) % 50 == 0:
                self.stdout.write(f"      ⏳ Явц: {idx + 1}/{total_rows} мөр...", ending='\r')

            # ID, Овог, Нэр, Сургууль авах
            try:
                # ID багана optional - None байж болно
                uid = row.get(id_col) if id_col else None
                if pd.isna(uid):
                    # ID байхгүй бол fallback column-үүдээс хайх
                    uid = row.get('ID', row.get('User ID', row.get('MMO ID')))
                ovog = str(row.get(last_name_col, '')).strip()
                ner = str(row.get(first_name_col, '')).strip()
                school_name = str(row.get(school_col, '')).strip() if school_col else None
            except Exception as e:
                # Багана олдсонгүй гэх мэт алдаа
                continue

            # Хэрэглэгч олох/үүсгэх
            user_before_count = User.objects.count() if not dry_run else 0
            user = self.get_user_smart(uid, ovog, ner, school_name, province_id, dry_run, category)

            # Шинэ хэрэглэгч үүсгэсэн эсэхийг шалгах
            if not dry_run and user and User.objects.count() > user_before_count:
                self.stats['users_created'] += 1

            if not user:
                error_info = {
                    'file': filename,
                    'sheet': source,
                    'row': idx + 2,
                    'id': uid if pd.notna(uid) else 'N/A',
                    'name': f"{ovog} {ner}".strip(),
                    'province_id': province_id,
                    'province_name': self.stats.get('current_province_name', 'Тодорхойгүй')
                }
                self.stats['users_not_found'].append(error_info)
                continue

            # Бүх оноо хоосон эсэхийг шалгах
            has_any_score = False
            for col_name, prob_num, prob in valid_score_cols:
                if pd.notna(row.get(col_name)):
                    has_any_score = True
                    break

            if not has_any_score:
                self.stdout.write(self.style.WARNING(
                    f"      ⚠️ Бүх оноо хоосон: {user.username} ({ovog} {ner}) - мөр алгасагдлаа"
                ))
                continue

            row_count += 1

            # UserMeta шалгах ба шаардлагатай бол үүсгэх
            if not dry_run:
                # UserMeta байхгүй бол үүсгэх (province мэдээлэл нөхөх)
                if not hasattr(user, 'data') or user.data is None:
                    # Province мэдээлэл байвал нөхөх
                    meta_province_id = province_id if province_id else None
                    meta = UserMeta.objects.create(
                        user=user,
                        reg_num='',  # default утга
                        province_id=meta_province_id
                    )
                    self.stdout.write(self.style.WARNING(
                        f"      ⚠️ UserMeta үүсгэв: {user.username} (Province: {meta_province_id})"
                    ))
                elif province_id and hasattr(user, 'data') and user.data and not user.data.province_id:
                    # UserMeta байгаа ч province байхгүй бол нөхөх
                    user.data.province_id = province_id
                    user.data.save(update_fields=['province_id'])
                    self.stdout.write(self.style.WARNING(
                        f"      ⚠️ Province нөхөв: {user.username} → {province_id}"
                    ))

            # Оноо хадгалах
            if not dry_run:
                with transaction.atomic():
                    for col_name, prob_num, prob in valid_score_cols:
                        score = row.get(col_name)
                        if pd.notna(score):
                            try:
                                score_val = float(score)
                                # Оноо хэт их эсэхийг шалгах
                                if score_val > prob.max_score:
                                    self.stdout.write(self.style.WARNING(
                                        f"      ⚠️ Оноо хэт их: {user.username}, Б{prob_num}: {score_val} > {prob.max_score}"
                                    ))
                                    score_val = prob.max_score  # Max score-оор солих

                                Result.objects.update_or_create(
                                    contestant=user,
                                    olympiad=olympiad,
                                    problem=prob,
                                    defaults={
                                        'score': score_val,
                                        'state': Result.States.approved
                                    }
                                )
                                scores_saved += 1
                            except (ValueError, TypeError) as e:
                                self.stdout.write(self.style.WARNING(
                                    f"      ⚠️ Оноо хөрвүүлэх алдаа: {user.username}, Б{prob_num}: '{score}'"
                                ))

        self.stats['total_rows_processed'] += row_count
        self.stats['total_scores_saved'] += scores_saved

        return row_count

    def romanize_name(self, name):
        """Кирилл үсгийг латинаар romanize хийх"""
        if not name:
            return ''
        result = []
        for char in name:
            if char in CYRILLIC_TO_LATIN:
                result.append(CYRILLIC_TO_LATIN[char])
            else:
                result.append(char)
        return ''.join(result)

    def normalize_name(self, name):
        """Нэрийг normalize хийх - хоосон зай, том/жижиг үсэг"""
        if not name:
            return ''
        # Хоосон зайг арилгах, жижиг үсэг болгох
        return ' '.join(name.strip().lower().split())

    def compare_names(self, name1, name2):
        """
        Хоёр нэрийг харьцуулж similarity (0-100) буцаана.
        Кирилл болон romanized хувилбаруудыг шалгана.
        """
        if not name1 or not name2:
            return 0

        # Normalize хийх
        n1 = self.normalize_name(name1)
        n2 = self.normalize_name(name2)

        # 1. Шууд харьцуулах
        direct_score = fuzz.ratio(n1, n2)

        # 2. Romanize хийж харьцуулах
        r1 = self.romanize_name(n1)
        r2 = self.romanize_name(n2)
        romanized_score = fuzz.ratio(r1, r2)

        # 3. Partial ratio (partial string matching)
        partial_score = fuzz.partial_ratio(n1, n2)

        # Хамгийн өндөр оноог авах
        return max(direct_score, romanized_score, partial_score)

    def get_user_smart(self, uid, last_name, first_name, school_name=None, province_id=None, dry_run=False, category=None):
        """
        Хэрэглэгч олох - ID, овог нэр, олон янзын форматыг дэмжинэ
        Хэрэв олдохгүй бол шинэ хэрэглэгч үүсгэнэ (dry_run=False үед)
        category: Sheet-ийн ангилал (C, D, E, F, S, T) - Grade/Level тодорхойлоход ашиглана
        """
        User = get_user_model()

        # 1. ID-аар хайх - янз бүрийн форматыг дэмжинэ
        if pd.notna(uid):
            # "U231632" гэх мэт текст ID
            if isinstance(uid, str):
                # U-аар эхэлбэл арилгах
                uid_clean = uid.strip().upper()
                if uid_clean.startswith('U'):
                    uid_clean = uid_clean[1:]
                # "." эсвэл хоосон бол алгасах
                if uid_clean in ['.', '', 'N/A', 'NA']:
                    uid = None
                else:
                    try:
                        uid = int(uid_clean)
                    except (ValueError, TypeError):
                        uid = None

            # Тоон ID
            if uid and pd.notna(uid):
                try:
                    uid_int = int(float(uid))
                    user = User.objects.get(id=uid_int)

                    # Овог нэр харьцуулах
                    if last_name and first_name:
                        # Овог нэрийг нэгтгэж харьцуулах
                        db_full_name = f"{user.last_name} {user.first_name}"
                        excel_full_name = f"{last_name} {first_name}"
                        similarity = self.compare_names(db_full_name, excel_full_name)

                        if similarity >= 85:
                            # 85%+ тохирч байна - хэрэглэгчийг ашиглах
                            self.stdout.write(self.style.SUCCESS(
                                f"      ✅ ID {uid_int} олдлоо: '{db_full_name}' ≈ '{excel_full_name}' ({similarity:.0f}%)"
                            ))

                            # Province мэдээлэл шинэчлэх (байвал)
                            user_province = getattr(user.data, 'province_id', None) if hasattr(user, 'data') and user.data else None
                            if province_id and user_province and int(user_province) != int(province_id):
                                if not dry_run:
                                    old_province = Province.objects.filter(id=user_province).first()
                                    new_province = Province.objects.filter(id=province_id).first()

                                    user.data.province_id = province_id
                                    user.data.save(update_fields=['province_id'])

                                    old_prov_name = old_province.name if old_province else str(user_province)
                                    new_prov_name = new_province.name if new_province else str(province_id)

                                    self.stdout.write(self.style.SUCCESS(
                                        f"      🔄 Province шинэчлэгдлээ: {old_prov_name} → {new_prov_name}"
                                    ))
                                    self.stats['province_updated'] += 1

                                    # Сургуулийг шинэчлэх
                                    self.update_user_school(user, new_province, school_name)

                            elif province_id and not user_province:
                                # Province байхгүй бол нөхөх
                                if not dry_run:
                                    user.data.province_id = province_id
                                    user.data.save(update_fields=['province_id'])
                                    self.stdout.write(self.style.SUCCESS(
                                        f"      ✅ Province нөхөгдлөө: {province_id}"
                                    ))
                                    self.stats['province_updated'] += 1

                            return user
                        else:
                            # 85%-аас бага - province-д овог нэрээр хайх
                            self.stdout.write(self.style.WARNING(
                                f"      ⚠️ ID {uid_int} олдсон ч нэр таарахгүй: '{db_full_name}' ≠ '{excel_full_name}' ({similarity:.0f}%)"
                            ))

                            # Province-д овог нэрээр хайх
                            if province_id:
                                existing_user = User.objects.filter(
                                    last_name__iexact=last_name,
                                    first_name__iexact=first_name,
                                    data__province_id=province_id
                                ).first()

                                if existing_user:
                                    self.stdout.write(self.style.SUCCESS(
                                        f"      ✅ Province-д ижил нэртэй хэрэглэгч олдлоо: {existing_user.username} (ID: {existing_user.id})"
                                    ))
                                    return existing_user

                            # Province-д олдсонгүй - шинэ хэрэглэгч үүсгэх рүү шилжих
                            self.stdout.write(self.style.WARNING(
                                f"      ⚠️ Тохирох хэрэглэгч олдсонгүй - Шинэ хэрэглэгч үүсгэнэ"
                            ))
                            # Шинэ хэрэглэгч үүсгэх рүү шилжих
                    else:
                        # Нэр өгөгдөөгүй бол ID-аар олдсон хэрэглэгчийг буцаах
                        return user

                except (User.DoesNotExist, ValueError, TypeError):
                    pass

        # 2. Овог нэрээр хайх
        elif last_name and first_name:
            if province_id:
                user = User.objects.filter(
                    last_name__iexact=last_name,
                    first_name__iexact=first_name,
                    data__province_id=province_id
                ).first()
                if user:
                    return user

        # 3. Хэрэглэгч олдоогүй - шинэ хэрэглэгч үүсгэх
        if last_name and first_name and not dry_run:
            # Түр username-тэй хэрэглэгч үүсгэх (ID авахын тулд)
            import time
            temp_username = f"temp_{int(time.time() * 1000000)}"

            user = User.objects.create(
                username=temp_username,
                first_name=first_name,
                last_name=last_name,
                email='auto-user@mmo.mn',  # Fixed email хаяг
                is_active=True
            )

            # ID авсны дараа username-ийг u+ID болгон шинэчлэх
            user.username = f"u{user.id}"
            user.save(update_fields=['username'])

            # Сургууль олох (хэрэв school_name байвал)
            school = None
            similarity = 0
            if school_name and pd.notna(school_name) and str(school_name).strip():
                school, similarity = self.find_school_by_name(str(school_name).strip(), province_id)

            # Сургууль олдоогүй бол province-ийн "Бусад" сургуульд бүртгэх
            if not school and province_id:
                busad_school = School.objects.filter(
                    province_id=province_id,
                    name="Бусад"
                ).first()

                if busad_school:
                    school = busad_school
                    similarity = 100  # "Бусад" сургууль гэдгийг тэмдэглэх
                    self.stdout.write(self.style.WARNING(
                        f"      ⚠️ Сургууль тодорхойлогдоогүй, '{busad_school.province.name}' аймгийн 'Бусад' сургуульд бүртгэгдлээ"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"      ⚠️ 'Бусад' сургууль олдсонгүй province_id={province_id}"
                    ))

            # Grade болон Level тодорхойлох (category-оос)
            grade_id, level_id = self.get_grade_and_level_from_category(category)

            # UserMeta үүсгэх
            # Province нь эхлээд файлаас, файлд байхгүй бол эхний хэрэглэгчдээс inference хийгдсэн
            # Сургуулийн province-ээс АВАХГҮЙ (сургууль province дотор хайгдсан)
            UserMeta.objects.create(
                user=user,
                reg_num='',  # Default утга
                province_id=province_id,  # Зөвхөн параметрээс авсан province
                school=school,
                grade_id=grade_id,
                level_id=level_id
            )

            # Сургуулийн group-д хэрэглэгчийг нэмэх
            if school:
                try:
                    if school.group:
                        school.group.user_set.add(user)
                        self.stdout.write(self.style.SUCCESS(
                            f"      ✅ Хэрэглэгчийг сургуулийн группд нэмлээ: {school.group.name}"
                        ))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(
                        f"      ⚠️ Группд нэмэхэд алдаа ({school.name}): {e}"
                    ))
                    # Устсан группын мэдээллийг статистикт нэмэх
                    missing_group_info = {
                        'school_id': school.id,
                        'school_name': school.name,
                        'province_id': province_id,
                        'province_name': self.stats.get('current_province_name', 'Тодорхойгүй'),
                        'error': str(e)
                    }
                    # Давхардахгүй байхын тулд school_id-аар шалгах
                    if not any(g['school_id'] == school.id for g in self.stats['missing_groups']):
                        self.stats['missing_groups'].append(missing_group_info)

            # Province мэдээлэл нэмэх
            province_info = ""
            if province_id:
                prov = Province.objects.filter(id=province_id).first()
                province_info = f", Аймаг: {prov.name if prov else province_id}"

            self.stdout.write(self.style.SUCCESS(
                f"      ✅ Шинэ хэрэглэгч үүсгэлээ: {last_name} {first_name} ({user.username}, ID: {user.id})" +
                (f", Сургууль: {school.name} ({similarity:.0f}%)" if school else "") +
                province_info
            ))

            self.stats['users_created'] += 1
            return user

        # Dry_run горимд эсвэл овог нэр байхгүй үед None буцаах
        if dry_run and last_name and first_name:
            self.stdout.write(self.style.WARNING(
                f"      ⚠️ [DRY RUN] Шинэ хэрэглэгч үүсгэх шаардлагатай: {last_name} {first_name}"
            ))

        return None

    def get_grade_and_level_from_category(self, category):
        """
        Sheet ангилалаас Grade болон Level тодорхойлох

        Ангиллын тайлбар:
        - B: 3-4 анги (Level 1, Grade 4)
        - C: 5-6 анги (Level 2, Grade 6)
        - D: 7-8 анги (Level 3, Grade 8)
        - E: 9-10 анги (Level 4, Grade 10)
        - F: 11-12 анги (Level 5, Grade 12)
        - S: Бага багш (Level 6, Grade 14 "Багш")
        - T: Дунд багш (Level 7, Grade 14 "Багш")

        Returns: (grade_id, level_id) эсвэл (None, None)
        """
        from accounts.models import Grade, Level

        # Category → (grade_search, level_id) mapping
        # Level ID нь database-тай яг тохирно
        CATEGORY_MAPPING = {
            'B': ('4-р анги', 1),   # Бага анги
            'C': ('6-р анги', 2),   # 5-6 анги
            'D': ('8-р анги', 3),   # 7-8 анги
            'E': ('10-р анги', 4),  # 9-10 анги
            'F': ('12-р анги', 5),  # 11-12 анги
            'S': ('Багш', 6),       # Бага багш (ББ)
            'T': ('Багш', 7),       # Дунд багш (ДБ)
        }

        if not category or category not in CATEGORY_MAPPING:
            return None, None

        grade_search, level_id = CATEGORY_MAPPING[category]

        # Grade олох - нэрээр хайна
        grade = Grade.objects.filter(name=grade_search).first()

        # Level олох - ID-аар шууд
        level = Level.objects.filter(id=level_id).first()

        return grade.id if grade else None, level.id if level else None

    def get_or_create_busad_school(self, province):
        """Тухайн дүүргийн 'Бусад' сургууль олох эсвэл үүсгэх"""
        school, created = School.objects.get_or_create(
            name=f"{province.name} - Бусад",
            province=province,
            defaults={'official_level_1': False, 'official_level_2': False}
        )
        if created:
            self.stdout.write(self.style.WARNING(f"      ⚠️ 'Бусад' сургууль үүслээ: {school.name} (ID: {school.id})"))
        return school

    def update_user_school(self, user, new_province, school_name=None):
        """
        Хэрэглэгчийн сургуулийг шинэчлэх.
        - Хэрэв school_name өгөгдсөн бол тухайн нэртэй сургууль хайх
        - Олдохгүй бол new_province-ийн "Бусад" сургуульд бүртгэх
        - Сургуулийн group-ийг шинэчлэх
        """
        old_school = user.data.school if hasattr(user, 'data') and user.data else None

        # Шинэ сургууль хайх
        new_school = None
        if school_name and pd.notna(school_name) and str(school_name).strip():
            new_school, similarity = self.find_school_by_name(str(school_name).strip(), new_province.id)
            if new_school and similarity >= 70:
                self.stdout.write(f"      → Сургууль олдлоо: {new_school.name} ({similarity:.0f}%)")

        # Олдоогүй бол "Бусад" сургуульд бүртгэх
        if not new_school:
            new_school = self.get_or_create_busad_school(new_province)
            self.stdout.write(f"      → '{new_province.name} - Бусад' сургуульд бүртгэгдлээ")

        # Хуучин сургуулийн group-ээс хасах
        if old_school and old_school.group:
            try:
                old_school.group.user_set.remove(user)
                self.stdout.write(f"      → Хуучин группээс хасагдлаа: {old_school.name}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"      ⚠️ Хуучин группээс хасахад алдаа: {e}"))

        # Шинэ сургууль болон group шинэчлэх
        user.data.school = new_school
        user.data.save(update_fields=['school'])

        # Шинэ сургуулийн group-д нэмэх
        if new_school and new_school.group:
            try:
                new_school.group.user_set.add(user)
                self.stdout.write(f"      → Шинэ группд нэмэгдлээ: {new_school.name}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"      ⚠️ Шинэ группд нэмэхэд алдаа: {e}"))

        return new_school

    def normalize_school_name(self, name):
        """
        Сургуулийн нэрийг нэг хэлбэрт оруулна:
        - Юникод normalize
        - Латин үсгийг кирилл рүү хөрвүүлэх
        - Түгээмэл үгсийг арилгах
        - Тоог жигд болгох
        """
        if not name:
            return ''
        n = unicodedata.normalize('NFKD', name).lower()

        # кирилл үсгийн ижилтгэл
        n = n.replace('ё', 'е').replace('ү', 'у').replace('ө', 'о')

        # латин үсгийг кирилл рүү ойролцоогоор хөрвүүлэх
        latin_map = {
            'a': 'а', 'b': 'б', 'v': 'в', 'g': 'г', 'd': 'д', 'e': 'е',
            'j': 'ж', 'z': 'з', 'i': 'и', 'k': 'к', 'l': 'л', 'm': 'м',
            'n': 'н', 'o': 'о', 'p': 'п', 'r': 'р', 's': 'с', 't': 'т',
            'u': 'у', 'f': 'ф', 'h': 'х', 'c': 'ц', 'y': 'й'
        }
        for latin, cyr in latin_map.items():
            n = re.sub(rf'\b{latin}\b', cyr, n)

        # '1-р', '2-р' гэх мэт илэрхийллийг жигд болгох
        n = re.sub(r'(\d+)(-р)?', r'\1', n)

        # түгээмэл үгсийг арилгах
        stop_words = ['ебс', 'ebs', 'school', 'surguuli', 'surguul', 'сургууль',
                      'дугаар', 'dugaar', '-', 'нийслэл', 'niislel', 'цогцолбор']
        for w in stop_words:
            n = n.replace(w, '')

        n = re.sub(r'\s+', ' ', n)
        return n.strip()

    def find_school_by_name(self, school_name, province_id=None):
        """
        Сургуулийн нэрээр хамгийн төстэй сургуулийг олох.

        ЧУХАЛ: Province нь эхлээд тогтоогдсон байх ёстой (файлаас эсвэл
        эхний хэрэглэгчдээс). Энэ функц зөвхөн тухайн province дотор
        сургууль хайна. Сургуулийн province-ээс province авахгүй.

        Хайлтын дараалал:
        1. Эхлээд province_id таарсан сургуулиудаас хайх (similarity >= 70%)
        2. Хэрэв олдохгүй бол бүх сургуулиудаас хайх (similarity >= 70%)

        Returns: (School, similarity_score) эсвэл (None, 0)
        """
        n1 = self.normalize_school_name(school_name)

        # 1-р шат: province_id таарсан сургуулиудаас хайх
        if province_id:
            candidates = School.objects.filter(province_id=province_id)
            best, best_score = self._find_best_school_match(n1, candidates)

            # Хэрэв сайн тохирол олдвол буцаах
            if best and best_score >= 70:
                return best, best_score

        # 2-р шат: province үл харгалзан хайх
        candidates = School.objects.all()
        best, best_score = self._find_best_school_match(n1, candidates)

        if best and best_score >= 70:
            return best, best_score

        return None, 0

    def _find_best_school_match(self, normalized_name, queryset):
        """Тухайн нэртэй хамгийн төстэй сургуулийг буцаана."""
        best, best_score = None, 0
        for school in queryset:
            n2 = self.normalize_school_name(school.name)
            score = fuzz.token_sort_ratio(normalized_name, n2)
            if score > best_score:
                best, best_score = school, score
        return best, best_score

    def infer_province_from_data(self, df, column_map):
        """
        Province_id олдохгүй бол эхний 3-5 сурагчийн province-ийг шалгах.
        Хамгийн олон гарсан province_id-г буцаана.
        """
        id_col = column_map['id_col']
        last_name_col = column_map['last_name_col']
        first_name_col = column_map['first_name_col']

        province_counts = {}
        checked_count = 0

        for idx, row in df.iterrows():
            if checked_count >= 5:  # Эхний 5 хүртэл хэрэглэгч шалгах
                break

            # Хэрэглэгч олох (province таних үед хэрэглэгч үүсгэхгүй)
            uid = row.get(id_col)
            ovog = str(row.get(last_name_col, '')).strip()
            ner = str(row.get(first_name_col, '')).strip()

            user = self.get_user_smart(uid, ovog, ner, dry_run=True)

            if user:
                # UserMeta-аас province_id авах
                try:
                    # User -> UserMeta (related_name='data')
                    if hasattr(user, 'data'):
                        prov_id = user.data.province_id
                        if prov_id:
                            province_counts[prov_id] = province_counts.get(prov_id, 0) + 1
                            checked_count += 1
                except Exception:
                    continue

        # Хамгийн олон гарсан province-ийг сонгох
        if province_counts:
            inferred_province = max(province_counts, key=province_counts.get)
            from accounts.models import Province
            province = Province.objects.filter(id=inferred_province).first()
            province_name = province.name if province else "Тодорхойгүй"
            # stats update хийх
            self.stats['current_province_id'] = inferred_province
            self.stats['current_province_name'] = province_name
            self.stdout.write(self.style.SUCCESS(
                f"      🔍 Датаас аймаг таньсан: {province_name} (ID: {inferred_province})"
            ))
            return inferred_province

        return None

    def extract_province_id(self, df):
        """
        Мэдээлэл sheet-ээс аймгийн ID-г авах.
        Дэмждэг форматууд:
        1. key/value: "Аймгийн ID" | 27
        2. Label дараа утга: "Аймгийн ID" | 27 (дараагийн баганад)
        """
        # 1. key/value column бүтэц шалгах
        if 'key' in df.columns and 'value' in df.columns:
            for _, row in df.iterrows():
                key_str = str(row.get('key', '')).lower().strip()
                if 'аймгийн id' in key_str or 'province id' in key_str:
                    try:
                        return int(float(row['value']))
                    except (ValueError, TypeError):
                        pass

        # 2. Мөр бүрийн нийлбэрт "аймгийн id"-г хайх
        for _, row in df.iterrows():
            row_str = [str(cell).lower().strip() for cell in row.values]
            for i, cell in enumerate(row_str):
                if "аймгийн id" in cell or "province id" in cell:
                    # Дараагийн баганаас утга авах
                    if i + 1 < len(row.values):
                        try:
                            val = row.values[i + 1]
                            if pd.notna(val):
                                return int(float(val))
                        except (ValueError, TypeError):
                            pass
                    # Эсвэл мөн баганад ":" дараа утга байж болно
                    # Жишээ: "Аймгийн ID: 27"
                    parts = cell.split(':')
                    if len(parts) > 1:
                        try:
                            return int(float(parts[1].strip()))
                        except (ValueError, TypeError):
                            pass
        return None

    def identify_category(self, name):
        for cat, pattern in self.CATEGORY_PATTERNS.items():
            if re.search(pattern, str(name), re.IGNORECASE): return cat
        return None

    def clean_dataframe(self, df, id_col, last_name_col, first_name_col):
        """
        DataFrame-ийг цэвэрлэх:
        1. Хоосон мөрүүдийг хасах (ID, Овог, Нэр бүгд хоосон)
        2. Merge хийсэн мөрүүдийг хасах
        """
        if len(df) == 0:
            return df

        # ID, Овог, Нэр багануудаас хоосон биш утгатай мөрүүдийг л авах
        mask = (
            df[id_col].notna() |
            df[last_name_col].notna() |
            df[first_name_col].notna()
        )

        cleaned_df = df[mask].copy()

        # Index дахин тооцох
        cleaned_df.reset_index(drop=True, inplace=True)

        return cleaned_df

    def detect_data_structure(self, df, category=None):
        """
        Ухаалаг DataFrame бүтэц таних систем.
        Returns: (data_df, column_map) эсвэл (None, None)
        column_map = {
            'id_col': column_name or index,
            'last_name_col': column_name or index,
            'first_name_col': column_name or index,
            'score_cols': [(col_name_or_index, problem_number), ...]
        }
        category: Ангиллын үсэг (C, D, E, F, T, S) - category-prefixed column names таних
        """
        # ID, Овог, Нэр, Сургууль, оноо багануудыг хайх түлхүүр үгс
        # Кирилл болон Латин хувилбаруудыг хоёуланг нь дэмжинэ
        ID_KEYWORDS = ['MMO ID', 'ММО ID', 'ID', 'USER ID', 'ММО №', 'БҮРТГЭЛИЙН №',
                       'MMO.MN', 'ДУГААР']
        LAST_NAME_KEYWORDS = ['ОВОГ', 'LAST NAME', 'ОРОЛЦОГЧИЙН ОВОГ']
        FIRST_NAME_KEYWORDS = ['НЭР', 'FIRST NAME', 'ОРОЛЦОГЧИЙН НЭР']
        SCHOOL_KEYWORDS = ['СУРГУУЛЬ', 'SCHOOL', 'СУРГУУЛИЙН НЭР', 'SCHOOL NAME']
        SCORE_KEYWORDS = ['№', 'Б', 'P', 'PROBLEM', 'БОДЛОГО']
        # Row number column-ийг танихгүй байх (Д.д, №, # гэх мэт)
        ROW_NUMBER_KEYWORDS = ['Д.Д', 'Д.д', '№', '#', 'ROW', 'NO']

        # 0. ЭХЛЭЭД df.columns шалгах - Pandas аль хэдийн header таньсан эсэхийг шалгах
        # Хэрэв column нэрүүд нь "Unnamed: 0", "0", "1" гэх мэт биш бол header байна
        column_names = [str(col) for col in df.columns]
        column_names_upper = [str(col).upper() for col in df.columns]

        # Column нэрүүд бодит нэр эсэхийг шалгах (тоо эсвэл "Unnamed" биш)
        has_real_columns = not all(
            str(col).startswith('Unnamed:') or str(col).isdigit()
            for col in df.columns
        )

        if has_real_columns and len(df) > 0:
            # df.columns дээр header хайх
            id_col_idx = self._find_column_by_keywords(column_names_upper, ID_KEYWORDS)
            last_name_col_idx = self._find_column_by_keywords(column_names_upper, LAST_NAME_KEYWORDS)
            first_name_col_idx = self._find_column_by_keywords(column_names_upper, FIRST_NAME_KEYWORDS)
            school_col_idx = self._find_column_by_keywords(column_names_upper, SCHOOL_KEYWORDS)

            # ID optional болгох - зөвхөн Овог, Нэр заавал байх ёстой
            if last_name_col_idx is not None and first_name_col_idx is not None:
                # Pandas аль хэдийн header-ийг таньсан!
                data_df = df.copy()

                # Оноо багануудыг олох
                score_cols = self._find_score_columns(column_names, column_names_upper, SCORE_KEYWORDS, category)

                column_map = {
                    'id_col': column_names[id_col_idx] if id_col_idx is not None else None,
                    'last_name_col': column_names[last_name_col_idx],
                    'first_name_col': column_names[first_name_col_idx],
                    'school_col': column_names[school_col_idx] if school_col_idx is not None else None,
                    'score_cols': [(column_names[col_idx], prob_num)
                                   for col_idx, prob_num in score_cols]
                }

                # Хоосон мөрүүдийг хасах
                data_df = self.clean_dataframe(
                    data_df,
                    column_map['id_col'],
                    column_map['last_name_col'],
                    column_map['first_name_col']
                )

                self.stdout.write(self.style.SUCCESS(
                    f"      ✨ Pandas-ын header ашигласан (стандарт формат)"
                ))
                return data_df, column_map

        # 1. df.iloc ашиглан мөр бүрийг шалгах
        for start_row in range(min(10, len(df))):  # Эхний 10 мөрийг шалгана
            row = df.iloc[start_row]

            # Мөрийн утгуудыг текст болгох - зөвхөн upper() хийх
            vals_raw = [str(v).strip() if pd.notna(v) else "" for v in row.values]
            vals_upper = [v.upper() for v in vals_raw]

            # 1. HEADER БАЙГАА ЭСЭХИЙГ ШАЛГАХ
            id_col = self._find_column_by_keywords(vals_upper, ID_KEYWORDS)
            last_name_col = self._find_column_by_keywords(vals_upper, LAST_NAME_KEYWORDS)
            first_name_col = self._find_column_by_keywords(vals_upper, FIRST_NAME_KEYWORDS)
            school_col = self._find_column_by_keywords(vals_upper, SCHOOL_KEYWORDS)

            # ID optional болгох - зөвхөн Овог, Нэр заавал байх ёстой
            if last_name_col is not None and first_name_col is not None:
                # Header олдлоо! Гэхдээ хоёр мөрт хуваагдсан эсэхийг шалгах

                # Эхлээд header мөр дээр аль хэдийн "№1", "№2" гэх мэт байгаа эсэхийг шалгах
                has_problem_numbers_in_header = any(
                    re.search(r'№\d+|Б\d+|P\d+', str(v)) for v in vals_raw
                )

                # 1a. ЭХЛЭЭД ХОЁР МӨРТ ХУВААГДСАН HEADER ЭСЭХИЙГ ШАЛГАХ
                if start_row < len(df) - 1 and not has_problem_numbers_in_header:
                    next_row = df.iloc[start_row + 1]
                    next_vals = [v for v in next_row.values]

                    # Дараагийн мөр нь тоонууд эсэхийг шалгах (асуултын дугаарууд)
                    if self._is_problem_number_row(next_vals):
                        # Хоёр мөрт хуваагдсан header!
                        # Баганын нэрүүдийг үүсгэх - хоосон column name-үүдийг автоматаар нэрлэх
                        column_names = []
                        for i, col_name in enumerate(vals_raw):
                            if pd.notna(col_name) and str(col_name).strip():
                                column_names.append(str(col_name).strip())
                            else:
                                # Хоосон column name - асуултын дугаараар нэрлэх
                                if i < len(next_vals) and pd.notna(next_vals[i]):
                                    # Арабын тоо шалгах
                                    try:
                                        prob_num = int(float(next_vals[i]))
                                        if 1 <= prob_num <= 20:
                                            column_names.append(f'№{prob_num}')
                                        else:
                                            column_names.append(f'Col_{i}')
                                    except (ValueError, TypeError):
                                        # Ром үсэг эсэхийг шалгах
                                        if isinstance(next_vals[i], str) and re.match(r'^[IVX]+$', str(next_vals[i]).strip().upper()):
                                            prob_num = self._roman_to_int(str(next_vals[i]).strip())
                                            if prob_num:
                                                column_names.append(f'№{prob_num}')
                                            else:
                                                column_names.append(f'Col_{i}')
                                        else:
                                            column_names.append(f'Col_{i}')
                                else:
                                    column_names.append(f'Col_{i}')

                        data_df = df.iloc[start_row + 2:].copy()
                        data_df.columns = column_names

                        # Асуултын дугаарыг дараагийн мөрөөс авах
                        score_cols = []
                        for col_idx, prob_num in enumerate(next_vals):
                            if pd.notna(prob_num) and col_idx >= max(id_col, last_name_col, first_name_col):
                                # Арабын тоо шалгах
                                try:
                                    prob_num_int = int(float(prob_num))
                                    if 1 <= prob_num_int <= 20:  # Асуултын дугаар 1-20 хооронд
                                        score_cols.append((column_names[col_idx], prob_num_int))
                                except (ValueError, TypeError):
                                    # Ром үсэг эсэхийг шалгах
                                    if isinstance(prob_num, str) and re.match(r'^[IVX]+$', str(prob_num).strip().upper()):
                                        prob_num_int = self._roman_to_int(str(prob_num).strip())
                                        if prob_num_int:
                                            score_cols.append((column_names[col_idx], prob_num_int))

                        column_map = {
                            'id_col': column_names[id_col] if id_col is not None else None,
                            'last_name_col': column_names[last_name_col],
                            'first_name_col': column_names[first_name_col],
                            'school_col': column_names[school_col] if school_col is not None else None,
                            'score_cols': score_cols
                        }

                        # Хоосон мөрүүдийг хасах
                        data_df = self.clean_dataframe(
                            data_df,
                            column_map['id_col'],
                            column_map['last_name_col'],
                            column_map['first_name_col']
                        )

                        self.stdout.write(self.style.SUCCESS(
                            f"      ✨ Хоёр мөрт хуваагдсан header олдлоо (мөр {start_row + 1}-{start_row + 2})"
                        ))
                        return data_df, column_map

                # 1b. ЭНГИЙН HEADER (нэг мөртэй)
                data_df = df.iloc[start_row + 1:].copy()
                data_df.columns = vals_raw

                # Оноо багануудыг олох
                score_cols = self._find_score_columns(vals_raw, vals_upper, SCORE_KEYWORDS, category)

                column_map = {
                    'id_col': vals_raw[id_col] if id_col is not None else None,
                    'last_name_col': vals_raw[last_name_col],
                    'first_name_col': vals_raw[first_name_col],
                    'school_col': vals_raw[school_col] if school_col is not None else None,
                    'score_cols': [(vals_raw[col_idx], prob_num)
                                   for col_idx, prob_num in score_cols]
                }

                # Хоосон мөрүүдийг хасах
                data_df = self.clean_dataframe(
                    data_df,
                    column_map['id_col'],
                    column_map['last_name_col'],
                    column_map['first_name_col']
                )

                self.stdout.write(self.style.SUCCESS(
                    f"      ✨ Header олдлоо (мөр {start_row + 1})"
                ))
                return data_df, column_map

            # 2. HEADER-ГҮЙ ШУУД ДАТА (СОНГИНОХАЙРХАН формат)
            # Формат: Д.д (тоо), ID (тоо), Овог (текст), Нэр (текст), оноонууд...
            if self._is_data_row_format(row.values):
                # Өгөгдөл шууд эхэлж байна
                data_df = df.iloc[start_row:].copy()

                # Баганы нэрийг автоматаар үүсгэх
                num_cols = len(data_df.columns)
                custom_cols = ['Д.д', 'MMO ID', 'Овог', 'Нэр']

                # Үлдсэн багануудыг тооцоолох - эхний 4-өөс хойш бол оноо эсвэл мэдээлэл
                for col_idx in range(4, num_cols):
                    # "Нийт" эсвэл сүүлийн багана биш бол оноо гэж үзэх
                    if col_idx == num_cols - 1:
                        custom_cols.append('Нийт')
                    elif col_idx < num_cols - 1:
                        custom_cols.append(f'№{col_idx - 3}')  # №1, №2, №3, №4
                    else:
                        custom_cols.append(f'Col_{col_idx}')

                data_df.columns = custom_cols[:num_cols]

                # Оноо багануудыг олох - №-аар эхэлдэг багануудыг авах
                score_cols = []
                for col_idx, col_name in enumerate(custom_cols):
                    if col_name.startswith('№'):
                        # №1 → 1
                        prob_num = int(col_name[1:])
                        score_cols.append((col_name, prob_num))

                column_map = {
                    'id_col': 'MMO ID',
                    'last_name_col': 'Овог',
                    'first_name_col': 'Нэр',
                    'school_col': None,  # Headerless format doesn't include school
                    'score_cols': score_cols
                }

                # Хоосон мөрүүдийг хасах
                data_df = self.clean_dataframe(
                    data_df,
                    column_map['id_col'],
                    column_map['last_name_col'],
                    column_map['first_name_col']
                )

                self.stdout.write(self.style.SUCCESS(
                    f"      ✨ Header-гүй дата танигдлаа (мөр {start_row + 1})"
                ))
                return data_df, column_map

        return None, None

    def _find_column_by_keywords(self, vals_upper, keywords):
        """
        Түлхүүр үгсээр багана олох.
        Урт keyword-үүдийг эхэнд шалгаж, богино keyword-үүдийг сүүлд шалгана.
        "ID" гэх мэт богино keyword нь зөвхөн яг тохирох үед л ажиллана.
        """
        # Keyword-үүдийг уртаар нь эрэмбэлэх (урт keyword эхэнд)
        sorted_keywords = sorted(keywords, key=len, reverse=True)

        for idx, val in enumerate(vals_upper):
            for keyword in sorted_keywords:
                # Богино keyword-ийн хувьд (2 тэмдэгт ба түүнээс бага) яг тохирох шаардлагатай
                if len(keyword) <= 2:
                    if val == keyword or val.strip() == keyword:
                        return idx
                else:
                    # Урт keyword-ийн хувьд substring match
                    if keyword in val:
                        return idx
        return None

    def _roman_to_int(self, roman):
        """Ром үсгийг тоо руу хөрвүүлэх (I→1, II→2, III→3, IV→4, ..., XX→20)"""
        roman_dict = {
            'I': 1, 'V': 5, 'X': 10
        }
        result = 0
        prev_value = 0

        for char in reversed(roman.upper()):
            if char not in roman_dict:
                return None
            value = roman_dict[char]
            if value < prev_value:
                result -= value
            else:
                result += value
            prev_value = value

        return result if 1 <= result <= 20 else None

    def _find_score_columns(self, vals_raw, vals_upper, score_keywords, category=None):
        """Оноо агуулсан багануудыг олох. Returns: [(col_idx, problem_number), ...]"""
        score_cols = []
        for idx, (raw_val, upper_val) in enumerate(zip(vals_raw, vals_upper)):
            # ЭХЛЭЭД: Category-prefixed pattern шалгах (C1, D2, E3, F4, T5, S6 гэх мэт)
            if category:
                # C1, D2, E3 гэх мэт pattern - category үсэг + тоо
                # Кирилл хувилбар ч дэмжих (Е1, С1 гэх мэт)
                cyrillic_variants = {
                    'C': '[CС]',  # Латин C эсвэл Кирилл С
                    'D': '[D]',
                    'E': '[EЕ]',  # Латин E эсвэл Кирилл Е
                    'F': '[F]',
                    'T': '[T]',
                    'S': '[S]',
                }
                cat_pattern = cyrillic_variants.get(category, f'[{category}]')
                # Pattern: C1, C2 эсвэл С1, С2 (кирилл)
                m = re.search(rf'^{cat_pattern}(\d+)$', upper_val.strip())
                if m:
                    prob_num = int(m.group(1))
                    if 1 <= prob_num <= 20:
                        score_cols.append((idx, prob_num))
                        continue

            # Ром үсэг формат шалгах: I, II, III, IV, V гэх мэт
            # Цэвэр Ром үсэг эсвэл түлхүүр үг + Ром үсэг (№I, №II, БI, БII гэх мэт)
            stripped_val = upper_val.strip()

            # Цэвэр Ром үсэг шалгах
            if re.match(r'^[IVX]+$', stripped_val):
                prob_num = self._roman_to_int(stripped_val)
                if prob_num:
                    score_cols.append((idx, prob_num))
                    continue

            # Түлхүүр үг + Ром үсэг шалгах (№I, №II, БI, P.I гэх мэт)
            for keyword in score_keywords:
                if keyword in upper_val:
                    # Түлхүүр үгийн дараах Ром үсгийг хайх
                    # №I, №II, Б.I, P I гэх мэт
                    m = re.search(rf'{re.escape(keyword)}[\s.]*([IVX]+)', upper_val)
                    if m:
                        prob_num = self._roman_to_int(m.group(1))
                        if prob_num:
                            score_cols.append((idx, prob_num))
                            break

            # Хуучин формат: №1, №2, Б1, Б2, P1, P2 гэх мэт
            for keyword in score_keywords:
                if keyword in upper_val:
                    # Тооноос гаргаж авах
                    m = re.search(r'(\d+)', raw_val)
                    if m:
                        prob_num = int(m.group(1))
                        if 1 <= prob_num <= 20:  # Асуултын дугаар 1-20 хооронд
                            score_cols.append((idx, prob_num))
                            break
        return score_cols

    def _is_problem_number_row(self, values):
        """Мөр нь асуултын дугаарууд (1, 2, 3, 4... эсвэл I, II, III, IV...) эсэхийг шалгах"""
        # ЭХЛЭЭД: Хэрэв багана 4 ба 5 (Овог, Нэр) текст агуулж байвал энэ нь дата мөр
        # Энэ нь асуултын дугаарын мөр биш
        if len(values) > 5:
            # Овог (index 4) болон Нэр (index 5) шалгах
            ovog = values[4] if len(values) > 4 else None
            ner = values[5] if len(values) > 5 else None

            # Хэрэв Овог эсвэл Нэр текст утга агуулж байвал энэ нь дата мөр
            if pd.notna(ovog) and isinstance(ovog, str) and len(str(ovog).strip()) > 0:
                # Тоо биш текст байвал дата мөр
                try:
                    float(str(ovog))
                except (ValueError, TypeError):
                    return False

            if pd.notna(ner) and isinstance(ner, str) and len(str(ner).strip()) > 0:
                # Тоо биш текст байвал дата мөр
                try:
                    float(str(ner))
                except (ValueError, TypeError):
                    return False

        numbers = []
        for i, v in enumerate(values):
            # Эхний 4 баганыг алгасах (Д.д, Овог, Нэр, ID)
            if i < 4:
                continue
            if pd.notna(v):
                # Арабын тоо шалгах
                try:
                    num = int(float(v))
                    if 1 <= num <= 20:
                        numbers.append(num)
                except (ValueError, TypeError):
                    # Ром үсэг эсэхийг шалгах
                    if isinstance(v, str) and re.match(r'^[IVX]+$', str(v).strip().upper()):
                        roman_num = self._roman_to_int(str(v).strip())
                        if roman_num:
                            numbers.append(roman_num)

        # Хамгийн багадаа 3 тоо байх ёстой
        if len(numbers) < 3:
            return False

        # Problem numbers нь ихэвчлэн давтагдахгүй эсвэл дараалсан байдаг
        # Хэрэв бүх тоонууд ижил байвал энэ нь магадгүй оноонууд (7, 7, 7, 7)
        unique_numbers = set(numbers)
        if len(unique_numbers) == 1 and numbers[0] > 4:
            # Бүх тоонууд ижил ба 4-өөс их (магадгүй оноо)
            return False

        # Problem numbers ихэвчлэн эхлээд 1-ээс эхэлдэг эсвэл дараалсан байдаг
        if 1 in numbers or len(unique_numbers) >= len(numbers) * 0.7:
            return True

        return False

    def _is_data_row_format(self, values):
        """
        Мөр нь шууд өгөгдөл эсэхийг шалгах.
        Формат: тоо, тоо, текст, текст, тоо/хоосон...
        """
        if len(values) < 4:
            return False

        def is_num(val):
            if pd.isna(val):
                return False
            try:
                float(str(val).replace('.0', ''))
                return True
            except:
                return False

        def is_text(val):
            return pd.notna(val) and isinstance(val, str) and len(str(val).strip()) > 0

        # Д.д (тоо), ID (тоо), Овог (текст), Нэр (текст)
        return (is_num(values[0]) and
                is_num(values[1]) and
                is_text(values[2]) and
                is_text(values[3]))


    def print_summary(self, dry_run):
        """Эцсийн дүгнэлт хэвлэх"""
        duration = (datetime.now() - self.stats['start_time']).total_seconds()

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("📊 ЭЦСИЙН ТАЙЛАН"))
        self.stdout.write("=" * 80)

        mode = "DRY RUN (Өгөгдөл хадгалаагүй)" if dry_run else "PRODUCTION (Өгөгдөл хадгалагдсан)"
        self.stdout.write(f"Горим: {mode}")
        self.stdout.write(f"Хугацаа: {duration:.1f} секунд")
        self.stdout.write("")
        self.stdout.write(f"✅ Нийт файл: {self.stats['total_files']}")
        self.stdout.write(f"✅ Нийт sheet: {self.stats['total_sheets']}")
        self.stdout.write(f"✅ Боловсруулсан мөр: {self.stats['total_rows_processed']}")

        if not dry_run:
            self.stdout.write(f"✅ Хадгалсан оноо: {self.stats['total_scores_saved']}")
            if self.stats['users_created'] > 0:
                self.stdout.write(f"✅ Үүсгэсэн хэрэглэгч: {self.stats['users_created']}")

        # Алдаануудыг хэвлэх
        if self.stats['users_not_found']:
            count = len(self.stats['users_not_found'])
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(f"⚠️ Хэрэглэгч олдоогүй: {count} тохиолдол"))

        if self.stats['province_updated'] > 0:
            self.stdout.write(self.style.SUCCESS(f"🔄 Province шинэчилсэн: {self.stats['province_updated']} хэрэглэгч"))

        if self.stats['olympiad_errors']:
            count = len(self.stats['olympiad_errors'])
            self.stdout.write(self.style.ERROR(f"❌ Олимпиад алдаа: {count} тохиолдол"))

        if self.stats['missing_groups']:
            count = len(self.stats['missing_groups'])
            self.stdout.write(self.style.WARNING(f"⚠️ Устсан групп: {count} сургууль"))

        self.stdout.write("=" * 80)

    def write_log_file(self, log_file, dry_run):
        """Алдааны мэдээллийг province бүрээр тусад нь log файлд бичих"""
        try:
            # Province бүрээр алдаануудыг бүлэглэх
            province_errors = {}

            # Хэрэглэгч олдоогүй
            for err in self.stats['users_not_found']:
                province_name = err.get('province_name', 'Тодорхойгүй')
                if province_name not in province_errors:
                    province_errors[province_name] = {
                        'users_not_found': [],
                        'olympiad_errors': [],
                        'missing_groups': []
                    }
                province_errors[province_name]['users_not_found'].append(err)

            # Олимпиад алдаа
            for err in self.stats['olympiad_errors']:
                province_name = err.get('province_name', 'Тодорхойгүй')
                if province_name not in province_errors:
                    province_errors[province_name] = {
                        'users_not_found': [],
                        'olympiad_errors': [],
                        'missing_groups': []
                    }
                province_errors[province_name]['olympiad_errors'].append(err)

            # Устсан групп
            for err in self.stats['missing_groups']:
                province_name = err.get('province_name', 'Тодорхойгүй')
                if province_name not in province_errors:
                    province_errors[province_name] = {
                        'users_not_found': [],
                        'olympiad_errors': [],
                        'missing_groups': []
                    }
                province_errors[province_name]['missing_groups'].append(err)

            # Province бүрээр файл үүсгэх
            log_files_created = []
            for province_name, errors in province_errors.items():
                # Province нэрийг файлын нэрт тохирох хэлбэрт оруулах
                if province_name is None:
                    province_name = 'Тодорхойгүй'
                safe_province_name = str(province_name).replace(' ', '_').replace('/', '_')
                province_log_file = f"import_log_{safe_province_name}.txt"

                with open(province_log_file, 'w', encoding='utf-8') as f:
                    f.write(f"=== IMPORT LOG - {province_name} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                    f.write(f"Mode: {'DRY RUN' if dry_run else 'PRODUCTION'}\n\n")

                    # Хэрэглэгч олдоогүй
                    if errors['users_not_found']:
                        f.write(f"\n{'='*80}\n")
                        f.write(f"ХЭРЭГЛЭГЧ ОЛДООГҮЙ ({len(errors['users_not_found'])} тохиолдол)\n")
                        f.write(f"{'='*80}\n")
                        for err in errors['users_not_found']:
                            f.write(f"Файл: {err['file']}\n")
                            f.write(f"Sheet: {err['sheet']}\n")
                            f.write(f"Мөр: {err['row']}\n")
                            f.write(f"ID: {err['id']}\n")
                            f.write(f"Нэр: {err['name']}\n")
                            f.write(f"{'-'*40}\n")

                    # Олимпиад алдаа
                    if errors['olympiad_errors']:
                        f.write(f"\n{'='*80}\n")
                        f.write(f"ОЛИМПИАД АЛДАА ({len(errors['olympiad_errors'])} тохиолдол)\n")
                        f.write(f"{'='*80}\n")
                        for err in errors['olympiad_errors']:
                            f.write(f"Файл: {err['file']}\n")
                            f.write(f"Sheet: {err['sheet']}\n")
                            f.write(f"Алдаа: {err['message']}\n")
                            f.write(f"{'-'*40}\n")

                    # Устсан групп
                    if errors['missing_groups']:
                        f.write(f"\n{'='*80}\n")
                        f.write(f"УСТСАН ГРУПП ({len(errors['missing_groups'])} сургууль)\n")
                        f.write(f"{'='*80}\n")
                        for err in errors['missing_groups']:
                            f.write(f"Сургуулийн ID: {err['school_id']}\n")
                            f.write(f"Сургуулийн нэр: {err['school_name']}\n")
                            f.write(f"Алдаа: {err['error']}\n")
                            f.write(f"{'-'*40}\n")

                log_files_created.append(province_log_file)

            # Нийт тайлан файл үүсгэх
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"=== НИЙТ ТАЙЛАН - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                f.write(f"Mode: {'DRY RUN' if dry_run else 'PRODUCTION'}\n\n")

                f.write(f"Нийт province: {len(province_errors)}\n")
                f.write(f"Нийт хэрэглэгч олдоогүй: {len(self.stats['users_not_found'])}\n")
                f.write(f"Нийт олимпиад алдаа: {len(self.stats['olympiad_errors'])}\n")
                f.write(f"Нийт устсан групп: {len(self.stats['missing_groups'])}\n")
                f.write(f"Нийт province шинэчилсэн: {self.stats['province_updated']}\n\n")

                f.write(f"Province бүрийн алдаануудын тоо:\n")
                f.write(f"{'='*80}\n")
                for province_name, errors in sorted(province_errors.items()):
                    total_errors = (len(errors['users_not_found']) +
                                  len(errors['olympiad_errors']) +
                                  len(errors['missing_groups']))
                    f.write(f"{province_name}: {total_errors} тохиолдол\n")
                    f.write(f"  - Хэрэглэгч олдоогүй: {len(errors['users_not_found'])}\n")
                    f.write(f"  - Олимпиад алдаа: {len(errors['olympiad_errors'])}\n")
                    f.write(f"  - Устсан групп: {len(errors['missing_groups'])}\n")
                    f.write(f"\n")

            self.stdout.write(self.style.SUCCESS(f"\n💾 Нийт тайлан файл бичигдлээ: {log_file}"))
            for province_log in log_files_created:
                self.stdout.write(self.style.SUCCESS(f"💾 Province лог файл бичигдлээ: {province_log}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Log файл бичихэд алдаа: {e}"))

    def move_files_to_processed(self, data_path):
        """Амжилттай импортолсон файлуудыг processed фолдерт хуулах"""
        import shutil

        # Processed фолдер үүсгэх
        processed_dir = os.path.join(data_path, 'processed')
        if not os.path.exists(processed_dir):
            os.makedirs(processed_dir)
            self.stdout.write(self.style.SUCCESS(f"\n📁 Processed фолдер үүсгэгдлээ: {processed_dir}"))

        moved_count = 0
        self.stdout.write(f"\n{'='*80}")
        self.stdout.write(self.style.MIGRATE_HEADING("📦 ФАЙЛ ХУУЛАЛТ"))
        self.stdout.write(f"{'='*80}")

        for filepath in self.stats['processed_files']:
            try:
                filename = os.path.basename(filepath)
                destination = os.path.join(processed_dir, filename)

                # Файл хуулах (davhar file-ийг overwrite хийх)
                shutil.move(filepath, destination)
                moved_count += 1
                self.stdout.write(self.style.SUCCESS(f"✅ {filename} → processed/"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ {filename} хуулахад алдаа: {e}"))

        self.stdout.write(f"\n💾 Нийт {moved_count}/{len(self.stats['processed_files'])} файл processed фолдерт хуулагдлаа")
        self.stdout.write(f"{'='*80}")