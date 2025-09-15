import re
from django.core.management.base import BaseCommand
from django.db.models import Count
from accounts.models import UserMeta
from django.contrib.auth.models import User

# python-Levenshtein сан суулгаагүй бол алдаа заахгүйгээр ажиллах боломжийг олгох
try:
    import Levenshtein
    LEVENSHTEIN_AVAILABLE = True
except ImportError:
    LEVENSHTEIN_AVAILABLE = False

class Command(BaseCommand):
    help = 'Давхардсан болон буруу форматтай регистрийн дугаартай хэрэглэгчдийг илрүүлнэ.'

    def handle(self, *args, **options):
        # --- 1. БУРУУ ФОРМАТТАЙ РЕГИСТРИЙН ДУГААР ШАЛГАХ ---
        self.stdout.write(self.style.NOTICE('Буруу форматтай регистрийн дугаартай хэрэглэгчдийг шалгаж байна...'))

        # Монгол регистрийн дугаарын зөв загвар (2 крилл үсэг, 8 тоо)
        reg_pattern = re.compile(r'^[А-ЯӨҮ]{2}\d{8}$')

        # Хоосон биш боловч буруу форматтай регистртэй хэрэглэгчдийг олох
        invalid_format_users = []
        all_metas = UserMeta.objects.exclude(reg_num__isnull=True).exclude(reg_num='').select_related('user')

        for meta in all_metas:
            if not reg_pattern.match(meta.reg_num):
                invalid_format_users.append(meta)

        if invalid_format_users:
            self.stdout.write(self.style.WARNING(f'Нийт {len(invalid_format_users)} хэрэглэгчийн регистрийн дугаар буруу форматтай байна:'))
            for meta in invalid_format_users:
                self.stdout.write(f"  - ID: {meta.user.id}, Нэр: {meta.user.get_full_name()}, Регистр: '{meta.reg_num}'")
        else:
            self.stdout.write(self.style.SUCCESS('Буруу форматтай регистрийн дугаар олдсонгүй.'))

        # --- 2. ДАВХАРДСАН РЕГИСТРИЙН ДУГААР ШАЛГАХ ---
        self.stdout.write(self.style.NOTICE('\nДавхардсан регистрийн дугаартай хэрэглэгчдийг хайж байна...'))

        duplicate_regs = UserMeta.objects.values('reg_num').annotate(
            reg_count=Count('reg_num')
        ).filter(
            reg_count__gt=1,
            reg_num__isnull=False
        ).exclude(
            reg_num=''
        )

        if not duplicate_regs.exists():
            self.stdout.write(self.style.SUCCESS('Давхардсан хэрэглэгч олдсонгүй.'))
            return

        self.stdout.write(self.style.WARNING(f'Нийт {duplicate_regs.count()} давхардсан регистрийн дугаар оллоо:'))

        for item in duplicate_regs:
            reg_num = item['reg_num']
            users = list(User.objects.filter(data__reg_num=reg_num))

            # Нэрсийн төстэй байдлын үнэлгээ
            similarity_note = ""
            if len(users) == 2 and LEVENSHTEIN_AVAILABLE:
                name1 = users[0].get_full_name().lower()
                name2 = users[1].get_full_name().lower()
                distance = Levenshtein.distance(name1, name2)
                if distance == 0:
                    similarity_note = "[НЭРС БҮРЭН ИЖИЛ]"
                elif distance <= 2: # 1-2 үсгийн зөрүүг ойролцоо гэж үзэх
                    similarity_note = f"[НЭРС ТӨСТЭЙ - Зөрүү: {distance}]"
                else:
                    similarity_note = "[НЭРС ЯЛГААТАЙ]"

            self.stdout.write(f"\n- Регистр: {reg_num} ({len(users)} хэрэглэгч) {similarity_note}")
            for user in users:
                self.stdout.write(f"  - ID: {user.id}, Нэр: {user.get_full_name()}, Username: {user.username}")

        self.stdout.write(self.style.SUCCESS('\nШалгаж дууслаа.'))