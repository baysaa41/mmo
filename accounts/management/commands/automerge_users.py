import re
import sys
import datetime
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction, models
from django.utils import timezone
from accounts.models import UserMeta
from olympiad.models import Result, Award, Comment, ScoreSheet
from schools.models import School

class Command(BaseCommand):
    help = 'Регистрийн дугаараар давхардсан хэрэглэгчдийг автоматаар нэгтгэнэ.'

    def add_arguments(self, parser):
        parser.add_argument('--reg-num', type=str, help='(Заавал биш) Нэгтгэх хэрэглэгчдийн давхардсан регистрийн дугаар')
        parser.add_argument(
            '--all',
            action='store_true',
            help='Бүх давхардсан регистртэй хэрэглэгчдийг шалгаж, автоматаар эсвэл асуулттайгаар нэгтгэх'
        )
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Баталгаажуулах асуултыг алгасах (зөвхөн --reg-num-тэй ашиглана)'
        )

    def handle(self, *args, **options):
        if options['all']:
            self._handle_all_duplicates(options)
        elif options['reg_num']:
            self._handle_single_reg_num(options)
        else:
            raise CommandError('Та --reg-num эсвэл --all параметрийн аль нэгийг заавал ашиглах ёстой.')

    def _handle_all_duplicates(self, options):
        self.stdout.write(self.style.NOTICE('Систем дэх бүх давхардлыг шалгаж байна...'))

        duplicate_regs = UserMeta.objects.values('reg_num').annotate(
            reg_count=models.Count('reg_num')
        ).filter(
            reg_count__gt=1,
            reg_num__isnull=False
        ).exclude(reg_num='')

        if not duplicate_regs:
            self.stdout.write(self.style.SUCCESS('Боловсруулах давхардал олдсонгүй.'))
            return

        reg_pattern = re.compile(r'^[А-ЯӨҮ]{2}\d{8}$')

        matching_name_groups = []
        mismatched_name_groups = []

        for item in duplicate_regs:
            reg_num = item['reg_num']
            if not reg_pattern.match(reg_num):
                self.stdout.write(self.style.WARNING(f"\n'{reg_num}' регистрийн дугаар буруу форматтай тул алгасаж байна."))
                continue

            users = list(User.objects.filter(data__reg_num=reg_num))
            first_user_fullname = (users[0].last_name.strip() + " " + users[0].first_name.strip()).lower()
            all_names_match = all((u.last_name.strip() + " " + u.first_name.strip()).lower() == first_user_fullname for u in users)

            if all_names_match:
                matching_name_groups.append(users)
            else:
                mismatched_name_groups.append(users)

        total_merged_groups = 0

        if matching_name_groups:
            self.stdout.write(self.style.NOTICE(f"\n--- 1-Р ҮЕ ШАТ: Овог, нэр бүрэн таарсан {len(matching_name_groups)} бүлэг хэрэглэгчийг автоматаар нэгтгэж байна ---"))
            for user_group in matching_name_groups:
                reg_num = user_group[0].data.reg_num
                self.stdout.write(self.style.NOTICE(f"\n'{reg_num}' регистртэй, овог нэр таарсан хэрэглэгчдийг нэгтгэж байна..."))
                merged, is_quit = self._merge_user_group(user_group, is_automatic=True)
                if merged:
                    total_merged_groups += 1
            self.stdout.write(self.style.SUCCESS('Автомат нэгтгэл дууслаа.'))

        if mismatched_name_groups:
            self.stdout.write(self.style.NOTICE(f"\n--- 2-Р ҮЕ ШАТ: Овог, нэр зөрүүтэй {len(mismatched_name_groups)} бүлэг хэрэглэгчийг гараар шийдвэрлэнэ үү ---"))
            for user_group in mismatched_name_groups:
                reg_num = user_group[0].data.reg_num
                self.stdout.write(self.style.WARNING(f"\n'{reg_num}' регистртэй хэрэглэгчдийн овог, нэр зөрүүтэй байна:"))
                merged, is_quit = self._merge_user_group(user_group, is_automatic=False)
                if is_quit:
                    return
                if merged:
                    total_merged_groups += 1

        self.stdout.write(self.style.SUCCESS(f'\nНийт {total_merged_groups} бүлэг давхардлыг амжилттай нэгтгэлээ.'))

    def _handle_single_reg_num(self, options):
        reg_num = options['reg_num']
        users = list(User.objects.filter(data__reg_num=reg_num))

        if len(users) < 2:
            raise CommandError(f"'{reg_num}' регистрийн дугаартай давхардсан хэрэглэгч олдсонгүй.")

        self._merge_user_group(users, is_automatic=options['no_input'])

    def _check_for_conflicts(self, primary_user, duplicate_users):
        for dup_user in duplicate_users:
            results_to_check = Result.objects.filter(contestant=dup_user)
            for dup_result in results_to_check:
                if Result.objects.filter(contestant=primary_user, olympiad=dup_result.olympiad, problem=dup_result.problem).exists():
                    return True
        return False

    def _merge_user_group(self, users, is_automatic=False):
        users.sort(key=lambda u: u.last_login or timezone.make_aware(datetime.datetime.min), reverse=True)
        primary_user = users[0]
        duplicate_users = users[1:]

        if self._check_for_conflicts(primary_user, duplicate_users):
            self.stdout.write(self.style.ERROR(
                f"  - АНХААР: ID={primary_user.id} болон бусад хэрэглэгчдийн хооронд дүнгийн давхцал олдлоо. "
                f"Энэ бүлгийг гараар шалгах шаардлагатай тул нэгтгэлгүй алгасав."
            ))
            return False, False

        while True:
            self.stdout.write(f"\n  - Үндсэн хэрэглэгчийн санал: {primary_user.get_full_name()} (ID: {primary_user.id})")
            for user in duplicate_users:
                self.stdout.write(f"  - Нэгтгэгдэх хэрэглэгч: {user.get_full_name()} (ID: {user.id})")

            if is_automatic:
                break

            choice = input('Дээрх үйлдлийг үргэлжлүүлэх үү? ([Y]es/[n]o/[c]hoose/[q]uit): ').lower().strip()

            if choice in ['y', 'yes', '']:
                break
            elif choice in ['n', 'no']:
                self.stdout.write(self.style.WARNING('  - Хэрэглэгч татгалзсан тул энэ бүлгийг алгаслаа.'))
                return False, False
            elif choice in ['q', 'quit']:
                self.stdout.write(self.style.ERROR('  - Хэрэглэгч коммандыг зогсоолоо.'))
                return False, True
            elif choice in ['c', 'choose']:
                try:
                    new_primary_id_str = input(f"  - Үндсэн болгох хэрэглэгчийн ID-г оруулна уу: ")
                    new_primary_id = int(new_primary_id_str)

                    new_primary_user = next((u for u in users if u.id == new_primary_id), None)

                    if new_primary_user:
                        primary_user = new_primary_user
                        duplicate_users = [u for u in users if u.id != new_primary_id]
                        self.stdout.write(self.style.SUCCESS(f"  - Үндсэн хэрэглэгчийг ID={new_primary_id}-р солилоо."))
                        if self._check_for_conflicts(primary_user, duplicate_users):
                            self.stdout.write(self.style.ERROR("  - АНХААР: Шинээр сонгосон үндсэн хэрэглэгчтэй дүнгийн давхцал үүслээ. Энэ бүлгийг нэгтгэх боломжгүй."))
                            return False, False
                        continue
                    else:
                        self.stdout.write(self.style.ERROR(f"  - Алдаа: '{new_primary_id}' ID-тай хэрэглэгч энэ бүлэгт байхгүй байна."))
                except (ValueError, TypeError):
                    self.stdout.write(self.style.ERROR("  - Алдаа: Та зөвхөн тоон ID оруулна уу."))
            else:
                self.stdout.write(self.style.ERROR("  - Буруу сонголт. 'y', 'n', 'c', эсвэл 'q' гэж оруулна уу."))

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

                if not best_data['user'].get('email') and user.email: best_data['user']['email'] = user.email
                if hasattr(user, 'data'):
                    meta = user.data
                    if not best_data['meta'].get('school') and meta.school: best_data['meta']['school'] = meta.school
                    if not best_data['meta'].get('grade') and meta.grade: best_data['meta']['grade'] = meta.grade
                    if not best_data['meta'].get('mobile') and meta.mobile: best_data['meta']['mobile'] = meta.mobile

            for field, value in best_data['user'].items(): setattr(primary_user, field, value)
            primary_user.save()
            for field, value in best_data['meta'].items(): setattr(primary_meta, field, value)
            primary_meta.save()

            for dup_user in duplicate_users:
                Result.objects.filter(contestant=dup_user).update(contestant=primary_user)
                Award.objects.filter(contestant=dup_user).update(contestant=primary_user)
                Comment.objects.filter(author=dup_user).update(author=primary_user)
                ScoreSheet.objects.filter(user=dup_user).update(user=primary_user)
                School.objects.filter(user=dup_user).update(user=primary_user)
                dup_user.delete()

        self.stdout.write(self.style.SUCCESS('  - Бүлэг амжилттай нэгтгэгдлээ!'))
        return True, False