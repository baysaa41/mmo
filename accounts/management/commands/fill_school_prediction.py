from django.core.management.base import BaseCommand
from accounts.models import SchoolData
from schools.models import School
from rapidfuzz import fuzz
import re
import unicodedata

def normalize_name(name: str) -> str:
    """
    Нэрийг нэг хэлбэрт оруулна:
    - Юникод normalize (ё -> е, ү -> у, ө -> о гэх мэт)
    - Латин үсгийг ойролцоогоор кирилл рүү хөрвүүлэх
    - 'ЕБС', 'surguuli', 'school' зэрэг давтагддаг үгсийг арилгах
    - '1-р сургууль' гэх мэт тоог жигд болгох
    """
    if not name:
        return ''
    n = unicodedata.normalize('NFKD', name).lower()

    # кирилл үсгийн ижилтгэл
    n = n.replace('ё', 'е').replace('ү', 'у').replace('ө', 'о')

    # латин үсгийг кирилл рүү ойролцоогоор хөрвүүлэх (хүссэнээрээ нэмж болно)
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
    stop_words = ['ебс', 'ebs', 'school', 'surguuli', 'surguul', 'сургууль', 'дугаар', 'dugaar', '-', 'нийслэл', 'niislel', 'цогцолбор']
    for w in stop_words:
        n = n.replace(w, '')

    n = re.sub(r'\s+', ' ', n)
    return n.strip()


class Command(BaseCommand):
    help = "SchoolData-г хамгийн төстэй School-оор автоматаар нөхнө (province буруу байж болох тохиолдолд)"

    def handle(self, *args, **options):
        count = 0
        for sd in SchoolData.objects.all():
            n1 = normalize_name(sd.school_name or '')

            # --- 1-р шат: province_id таарсан сургуулиудаас хайх ---
            candidates = School.objects.filter(province_id=sd.province_id)
            best, best_score = self.find_best_match(n1, candidates)

            # --- 2-р шат: province үл харгалзан хайх ---
            if best_score < 70:
                candidates = School.objects.all()
                best, best_score = self.find_best_match(n1, candidates)

            if best and best_score >= 70:
                sd.school_id = best.id
                sd.school_name_prediction = best.name
                sd.province_id_prediction = best.province_id
                sd.similarity = best_score
                sd.save(update_fields=[
                    'school_id',
                    'school_name_prediction',
                    'province_id_prediction',
                    'similarity'
                ])
                count += 1
                self.stdout.write(
                    f"{sd.id}: {sd.school_name} → {best.name} "
                    f"(Province guess {best.province_id}, Similarity {best_score:.1f}%)"
                )

        self.stdout.write(self.style.SUCCESS(
            f"Амжилттай шинэчилсэн мөрийн тоо: {count}"
        ))

    def find_best_match(self, n1: str, queryset):
        """Тухайн нэртэй хамгийн төстэй сургуулийг буцаана."""
        best, best_score = None, 0
        for s in queryset:
            n2 = normalize_name(s.name)
            score = fuzz.token_sort_ratio(n1, n2)
            if score > best_score:
                best, best_score = s, score
        return best, best_score
