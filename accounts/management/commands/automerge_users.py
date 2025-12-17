import re
import sys
import datetime
import unicodedata
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction, models
from django.utils import timezone
from accounts.models import UserMeta
from olympiad.models import Result, Award, Comment, ScoreSheet
from schools.models import School
from rapidfuzz import fuzz

# Кирилл → Латин хөрвүүлэлтийн толь бичиг
CYR_TO_LAT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'j','з':'z',
    'и':'i','й':'i','к':'k','л':'l','м':'m','н':'n','о':'o','ө':'o','п':'p',
    'р':'r','с':'s','т':'t','у':'u','ү':'u','ф':'f','х':'kh','ц':'ts','ч':'ch',
    'ш':'sh','щ':'sh','ъ':'','ы':'i','ь':'','э':'e','ю':'yu','я':'ya'
}

def normalize_fullname(last_name: str, first_name: str) -> str:
    """
    Овог нэрийг нормчлож, кирилл үсгийг латин болгоно.
    Жишээ: "Баярсайхан Дорж" → "bayarsaikhan dorj"
    """
    fullname = f"{last_name.strip()} {first_name.strip()}"
    fullname = unicodedata.normalize('NFKD', fullname)
    fullname = ''.join(ch for ch in fullname if not unicodedata.combining(ch))
    fullname = fullname.lower()
    fullname = ''.join(CYR_TO_LAT.get(ch, ch) for ch in fullname)
    fullname = re.sub(r'\s+', ' ', fullname).strip()
    return fullname

def normalize_reg_num(reg_num: str) -> str:
    """
    Регистрийн дугаарыг нормчилно.
    Жишээ: "АБ12345678" → "ab12345678"
    """
    if not reg_num:
        return ''
    reg_num = reg_num.strip().lower()
    prefix = reg_num[:2]
    suffix = reg_num[2:]
    normalized_prefix = ''.join(CYR_TO_LAT.get(ch, ch) for ch in prefix)
    return normalized_prefix + suffix

def names_are_similar(name1: str, name2: str, threshold: int = 90) -> tuple:
    """Хоёр нэрийг fuzzy matching ашиглан харьцуулна."""
    if name1 == name2:
        return True, 100
    score = fuzz.token_sort_ratio(name1, name2)
    return score >= threshold, score

def check_name_swap(user1, user2) -> tuple:
    """Овог нэр солигдсон эсэхийг шалгана."""
    norm1_ln = normalize_fullname(user1.last_name, "").strip()
    norm1_fn = normalize_fullname("", user1.first_name).strip()
    norm2_ln = normalize_fullname(user2.last_name, "").strip()
    norm2_fn = normalize_fullname("", user2.first_name).strip()

    if norm1_ln == norm2_fn and norm1_fn == norm2_ln:
        return True, "Овог нэр солигдсон байна"
    return False, ""

class Command(BaseCommand):
    help = 'Регистрийн дугаараар давхардсан хэрэглэгчдийг автоматаар нэгтгэнэ.'

    def add_arguments(self, parser):
        parser.add_argument('--reg-num', type=str, help='Нэгтгэх хэрэглэгчдийн давхардсан регистрийн дугаар')
        parser.add_argument('--all', action='store_true', help='Бүх давхардсан регистртэй хэрэглэгчдийг шалгах')
        parser.add_argument('--no-input', action='store_true', help='Баталгаажуулах асуултыг алгасах')
        parser.add_argument('--similarity-threshold', type=int, default=90, help='Fuzzy matching оноо (0-100)')

    def handle(self, *args, **options):
        self.similarity_threshold = options['similarity_threshold']
        if options['all']:
            self._handle_all_duplicates(options)
        elif options['reg_num']:
            self._handle_single_reg_num(options)
        else:
            raise CommandError('Та --reg-num эсвэл --all параметрийн аль нэгийг заавал ашиглах ёстой.')

    def _handle_all_duplicates(self, options):
        self.stdout.write(self.style.NOTICE(f'Систем дэх бүх давхардлыг шалгаж байна... (Fuzzy threshold: {self.similarity_threshold})'))

        all_user_metas = UserMeta.objects.exclude(reg_num__isnull=True).exclude(reg_num='')
        normalized_reg_groups = {}
        for meta in all_user_metas:
            normalized = normalize_reg_num(meta.reg_num)
            if normalized not in normalized_reg_groups:
                normalized_reg_groups[normalized] = []
            normalized_reg_groups[normalized].append(meta)

        duplicate_groups = {k: v for k, v in normalized_reg_groups.items() if len(v) > 1}

        if not duplicate_groups:
            self.stdout.write(self.style.SUCCESS('Боловсруулах давхардал олдсонгүй.'))
            return

        reg_pattern = re.compile(r'^[a-z]{2,3}\d{8}$')
        exact_match_groups = []
        fuzzy_match_groups = []
        name_swap_groups = []
        mismatched_name_groups = []

        for normalized_reg, user_metas in duplicate_groups.items():
            if not reg_pattern.match(normalized_reg):
                original_regs = [um.reg_num for um in user_metas]
                self.stdout.write(self.style.WARNING(f"\n'{', '.join(original_regs)}' буруу форматтай тул алгасаж байна."))
                continue

            users = [um.user for um in user_metas if um.user]
            if len(users) < 2:
                continue

            first_user_normalized = normalize_fullname(users[0].last_name, users[0].first_name)

            all_exact_match = all(normalize_fullname(u.last_name, u.first_name) == first_user_normalized for u in users)

            if all_exact_match:
                exact_match_groups.append(users)
                continue

            if len(users) == 2:
                is_swapped, swap_msg = check_name_swap(users[0], users[1])
                if is_swapped:
                    name_swap_groups.append(users)
                    continue

            all_fuzzy_match = True
            similarity_scores = []
            for u in users[1:]:
                u_normalized = normalize_fullname(u.last_name, u.first_name)
                is_similar, score = names_are_similar(first_user_normalized, u_normalized, self.similarity_threshold)
                similarity_scores.append(score)
                if not is_similar:
                    all_fuzzy_match = False
                    break

            if all_fuzzy_match:
                fuzzy_match_groups.append((users, min(similarity_scores)))
            else:
                mismatched_name_groups.append(users)

        total_merged_groups = 0

        if exact_match_groups:
            self.stdout.write(self.style.NOTICE(f"\n--- ШАТ 1: Овог нэр бүрэн адил ({len(exact_match_groups)} бүлэг) ---"))
            for user_group in exact_match_groups:
                reg_nums = list(set([u.data.reg_num for u in user_group if hasattr(u, 'data')]))
                normalized_reg = normalize_reg_num(reg_nums[0]) if reg_nums else ''
                self.stdout.write(self.style.SUCCESS(f"\nРегистр: {', '.join(reg_nums)} → '{normalized_reg}'"))
                for u in user_group:
                    normalized = normalize_fullname(u.last_name, u.first_name)
                    self.stdout.write(f"  ✓ ID {u.id}: '{u.last_name} {u.first_name}' → '{normalized}'")
                merged, is_quit = self._merge_user_group(user_group, is_automatic=True)
                if merged:
                    total_merged_groups += 1

        if name_swap_groups:
            self.stdout.write(self.style.NOTICE(f"\n--- ШАТ 2: Овог нэр солигдсон ({len(name_swap_groups)} бүлэг) - АВТОМАТ НЭГТГЭНЭ ---"))
            for user_group in name_swap_groups:
                reg_nums = list(set([u.data.reg_num for u in user_group if hasattr(u, 'data')]))
                normalized_reg = normalize_reg_num(reg_nums[0]) if reg_nums else ''
                self.stdout.write(self.style.SUCCESS(f"\nРегистр: {', '.join(reg_nums)} → '{normalized_reg}' - Овог нэр солигдсон"))
                for u in user_group:
                    self.stdout.write(f"  ✓ ID {u.id}: Овог='{u.last_name}', Нэр='{u.first_name}'")
                merged, is_quit = self._merge_user_group(user_group, is_automatic=True)
                if merged:
                    total_merged_groups += 1

        if fuzzy_match_groups:
            self.stdout.write(self.style.NOTICE(f"\n--- ШАТ 3: Ойролцоо нэртэй ({len(fuzzy_match_groups)} бүлэг) ---"))
            for user_group, min_score in fuzzy_match_groups:
                reg_nums = list(set([u.data.reg_num for u in user_group if hasattr(u, 'data')]))
                normalized_reg = normalize_reg_num(reg_nums[0]) if reg_nums else ''
                self.stdout.write(self.style.WARNING(f"\nРегистр: {', '.join(reg_nums)} → '{normalized_reg}' ({min_score}%)"))
                for u in user_group:
                    normalized = normalize_fullname(u.last_name, u.first_name)
                    self.stdout.write(f"  ~ ID {u.id}: '{u.last_name} {u.first_name}' → '{normalized}'")
                merged, is_quit = self._merge_user_group(user_group, is_automatic=False)
                if is_quit:
                    return
                if merged:
                    total_merged_groups += 1

        if mismatched_name_groups:
            self.stdout.write(self.style.NOTICE(f"\n--- ШАТ 4: Овог нэр зөрүүтэй ({len(mismatched_name_groups)} бүлэг) ---"))
            for user_group in mismatched_name_groups:
                reg_nums = list(set([u.data.reg_num for u in user_group if hasattr(u, 'data')]))
                normalized_reg = normalize_reg_num(reg_nums[0]) if reg_nums else ''
                self.stdout.write(self.style.ERROR(f"\nРегистр: {', '.join(reg_nums)} → '{normalized_reg}'"))
                for u in user_group:
                    normalized = normalize_fullname(u.last_name, u.first_name)
                    self.stdout.write(f"  ✗ ID {u.id}: '{u.last_name} {u.first_name}' → '{normalized}'")
                merged, is_quit = self._merge_user_group(user_group, is_automatic=False)
                if is_quit:
                    return
                if merged:
                    total_merged_groups += 1

        self.stdout.write(self.style.SUCCESS(f'\n🎉 Нийт {total_merged_groups} бүлэг давхардлыг амжилттай нэгтгэлээ.'))

    def _handle_single_reg_num(self, options):
        reg_num = options['reg_num']
        users = list(User.objects.filter(data__reg_num=reg_num))
        if len(users) < 2:
            raise CommandError(f"'{reg_num}' регистрийн дугаартай давхардсан хэрэглэгч олдсонгүй.")
        self._merge_user_group(users, is_automatic=options['no_input'])

    def _check_for_conflicts(self, primary_user, duplicate_users):
        """Дүнгийн давхцал шалгаж, зөвхөн өөр утгатай давхцлыг буцаана."""
        real_conflicts = []

        for dup_user in duplicate_users:
            results_to_check = Result.objects.filter(contestant=dup_user).select_related('olympiad', 'problem')

            for dup_result in results_to_check:
                primary_result = Result.objects.filter(
                    contestant=primary_user,
                    olympiad=dup_result.olympiad,
                    problem=dup_result.problem
                ).first()

                if primary_result:
                    # Хариулт ЭСВЭЛ оноо өөр байвал л давхцал гэж үзнэ
                    if (primary_result.answer != dup_result.answer or
                        primary_result.score != dup_result.score):
                        real_conflicts.append({
                            'dup_user': dup_user,
                            'olympiad': dup_result.olympiad,
                            'problem': dup_result.problem,
                            'primary_score': primary_result.score,
                            'dup_score': dup_result.score,
                            'primary_answer': primary_result.answer,
                            'dup_answer': dup_result.answer,
                        })

        return real_conflicts

    def _merge_user_group(self, users, is_automatic=False):
        users.sort(key=lambda u: u.last_login or timezone.make_aware(datetime.datetime.min), reverse=True)
        primary_user = users[0]
        duplicate_users = users[1:]

        conflicts = self._check_for_conflicts(primary_user, duplicate_users)

        if conflicts:
            self.stdout.write(self.style.ERROR(f"\n  ⚠️  АНХААР: Дүнгийн давхцал олдлоо!"))
            self.stdout.write(self.style.ERROR(f"  Үндсэн хэрэглэгч: {primary_user.last_name} {primary_user.first_name} (ID: {primary_user.id})"))

            for idx, conflict in enumerate(conflicts, 1):
                self.stdout.write(self.style.WARNING(f"\n  Давхцал #{idx}:"))
                self.stdout.write(f"    - Олимпиад: {conflict['olympiad'].name}")
                self.stdout.write(f"    - Бодлого: №{conflict['problem'].order}")
                self.stdout.write(f"    - {primary_user.last_name} {primary_user.first_name} (ID {primary_user.id}): Хариулт={conflict['primary_answer']}, Оноо={conflict['primary_score']}")
                self.stdout.write(f"    - {conflict['dup_user'].last_name} {conflict['dup_user'].first_name} (ID {conflict['dup_user'].id}): Хариулт={conflict['dup_answer']}, Оноо={conflict['dup_score']}")

            self.stdout.write(self.style.ERROR(f"\n  ❌ Энэ бүлгийг автоматаар нэгтгэх боломжгүй. Гараар шалгаж, database-аас засна уу."))
            return False, False

        while True:
            self.stdout.write(f"\n  - Үндсэн хэрэглэгч: {primary_user.last_name} {primary_user.first_name} (ID: {primary_user.id})")
            for user in duplicate_users:
                self.stdout.write(f"  - Нэгтгэгдэх: {user.last_name} {user.first_name} (ID: {user.id})")

            if is_automatic:
                break

            choice = input('Continue? ([Y]es/[n]o/[c]hoose/[q]uit): ').lower().strip()

            if choice in ['y', 'yes', '']:
                break
            elif choice in ['n', 'no']:
                self.stdout.write(self.style.WARNING('  - Татгалзсан'))
                return False, False
            elif choice in ['q', 'quit']:
                self.stdout.write(self.style.ERROR('  - Зогсоосон'))
                return False, True
            elif choice in ['c', 'choose']:
                self.stdout.write(self.style.NOTICE("\nҮндсэн хэрэглэгчийг сонгоно уу:"))
                for idx, user in enumerate(users, start=1):
                    last_login_str = user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Нэвтрээгүй'
                    self.stdout.write(f"  [{idx}] ID {user.id}: {user.last_name} {user.first_name} ({last_login_str})")
                try:
                    choice_num = input(f"\nСонголт (1-{len(users)}): ").strip()
                    choice_idx = int(choice_num) - 1
                    if 0 <= choice_idx < len(users):
                        new_primary_user = users[choice_idx]
                        primary_user = new_primary_user
                        duplicate_users = [u for u in users if u.id != new_primary_user.id]
                        self.stdout.write(self.style.SUCCESS(f"  ✓ '{new_primary_user.last_name} {new_primary_user.first_name}' (ID={new_primary_user.id})"))

                        # Шинэ үндсэн хэрэглэгчээр давхцал дахин шалгах
                        new_conflicts = self._check_for_conflicts(primary_user, duplicate_users)
                        if new_conflicts:
                            self.stdout.write(self.style.ERROR("  - АНХААР: Шинэ үндсэн хэрэглэгчтэй дүнгийн давхцал үүслээ."))

                            for idx, conflict in enumerate(new_conflicts, 1):
                                self.stdout.write(self.style.WARNING(f"\n  Давхцал #{idx}:"))
                                self.stdout.write(f"    - Олимпиад: {conflict['olympiad'].name}")
                                self.stdout.write(f"    - Бодлого: №{conflict['problem'].order}")
                                self.stdout.write(f"    - Хариулт: {conflict['primary_answer']} vs {conflict['dup_answer']}")

                            return False, False
                        continue
                    else:
                        self.stdout.write(self.style.ERROR(f"  - Алдаа: 1-{len(users)} хооронд сонгоно уу."))
                except (ValueError, TypeError):
                    self.stdout.write(self.style.ERROR("  - Алдаа: Тоон дугаар оруулна уу."))
            else:
                self.stdout.write(self.style.ERROR("  - Буруу сонголт."))

        with transaction.atomic():
            primary_meta, _ = UserMeta.objects.get_or_create(user=primary_user)
            best_data = {'user': {}, 'meta': {}}
            all_users_for_merge = [primary_user] + duplicate_users

            cyrillic_pattern = re.compile(r'[а-яА-ЯөӨүҮ]')
            def is_cyrillic(s):
                return s and bool(cyrillic_pattern.search(s))

            for user in all_users_for_merge:
                current_best_fn = best_data['user'].get('first_name')
                if user.first_name and (not current_best_fn or (is_cyrillic(user.first_name) and not is_cyrillic(current_best_fn))):
                    best_data['user']['first_name'] = user.first_name

                current_best_ln = best_data['user'].get('last_name')
                if user.last_name and (not current_best_ln or (is_cyrillic(user.last_name) and not is_cyrillic(current_best_ln))):
                    best_data['user']['last_name'] = user.last_name

                if not best_data['user'].get('email') and user.email:
                    best_data['user']['email'] = user.email
                if hasattr(user, 'data'):
                    meta = user.data
                    if not best_data['meta'].get('school') and meta.school:
                        best_data['meta']['school'] = meta.school
                    if not best_data['meta'].get('grade') and meta.grade:
                        best_data['meta']['grade'] = meta.grade
                    if not best_data['meta'].get('mobile') and meta.mobile:
                        best_data['meta']['mobile'] = meta.mobile

            for field, value in best_data['user'].items():
                setattr(primary_user, field, value)
            primary_user.save()
            for field, value in best_data['meta'].items():
                setattr(primary_meta, field, value)
            primary_meta.save()

            for dup_user in duplicate_users:
                duplicate_user_groups = dup_user.groups.all()
                primary_user.groups.add(*duplicate_user_groups)
                Result.objects.filter(contestant=dup_user).update(contestant=primary_user)
                Award.objects.filter(contestant=dup_user).update(contestant=primary_user)
                Comment.objects.filter(author=dup_user).update(author=primary_user)
                ScoreSheet.objects.filter(user=dup_user).update(user=primary_user)
                School.objects.filter(user=dup_user).update(user=primary_user)
                dup_user.delete()

        self.stdout.write(self.style.SUCCESS('  ✅ Амжилттай нэгтгэлээ!'))
        return True, False