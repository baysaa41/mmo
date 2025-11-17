import re
import unicodedata
from rapidfuzz import fuzz
from schools.models import School

CYR_TO_LAT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'j','з':'z',
    'и':'i','й':'i','к':'k','л':'l','м':'m','н':'n','о':'o','ө':'o','п':'p',
    'р':'r','с':'s','т':'t','у':'u','ү':'u','ф':'f','х':'kh','ц':'ts','ч':'ch',
    'ш':'sh','щ':'sh','ъ':'','ы':'i','ь':'','э':'e','ю':'yu','я':'ya'
}

# Roman → arab conversion helper
ROMAN_MAP = {
    'M':1000,'CM':900,'D':500,'CD':400,'C':100,'XC':90,'L':50,
    'XL':40,'X':10,'IX':9,'V':5,'IV':4,'I':1
}

def roman_to_int(roman: str) -> int:
    """Simple Roman numeral to int converter (supports up to several thousand)."""
    i, num = 0, 0
    roman = roman.upper()
    while i < len(roman):
        if i+1 < len(roman) and roman[i:i+2] in ROMAN_MAP:
            num += ROMAN_MAP[roman[i:i+2]]
            i += 2
        else:
            num += ROMAN_MAP.get(roman[i], 0)
            i += 1
    return num

# olon shatlaltai ner gargaj avaad shalgaj bolno
def normalize_name(name: str) -> str:
    """
    Сургуулийн нэрийг латин болгож, тоон утгыг бүхэлд нь хадгална.
    'ЕБ-ын 1 дүгээр сургууль' гэх мэт нэрийг зөвхөн '1' болгоно.
    """
    if not name:
        return ''

    n = unicodedata.normalize('NFKD', name)
    n = ''.join(ch for ch in n if not unicodedata.combining(ch))
    n = n.lower()

    # Кирилл үсгийг латин руу хөрвүүлэх
    n = ''.join(CYR_TO_LAT.get(ch, ch) for ch in n)

    def replace_roman(match):
        return str(roman_to_int(match.group(0)))
    n = re.sub(r'\b[mdclxvi]+\b', replace_roman, n, flags=re.IGNORECASE)

    n = re.sub(r'neg\s*dugeer', '1', n)
    n = re.sub(r'hoyor\s*dugaar', '2', n)
    n = re.sub(r'gurav\s*dugaar', '3', n)

    # ЕБ-ын / ЕБ-ийн / ЕБ-ийнх зэрэг бүх хэлбэрийг арилгах
    n = re.sub(r'\beb[- ]?(iin|iinx|yn|in)\b', '', n)

    # 1 дүгээр / 1 дугаар / 1-р / №1 / No.1 / number 1 зэрэг хэлбэрийг нэгтгэх
    n = re.sub(r'-', r' ', n)
    n = re.sub(r'(\d+)\s*(dugaar|dugeer|dugaarin|dugeerin)\b', r'\1', n)
    n = re.sub(r'(\d+)\s*[-]?\s*r\b', r'\1', n)
    n = re.sub(r'№\s*(\d+)', r'\1', n)
    n = re.sub(r'no\.?\s*(\d+)', r'\1', n)
    n = re.sub(r'number\s*(\d+)', r'\1', n)
    # n = re.sub(r'(\d+)\s*-\s*surguuli', r'\1', n)  # 1-сургууль → 1

    # Давтагддаг үгсийг арилгах
    stop_words = [
        '.',',','school','surguuli','surguul','sumin','aimgin','sum','aimag','ebs','eb','arvaikheer','buren','dund',
        'laboratori','laboratoroi','labortor','neremjit','ulsiin','terguunii','eronkhii','bolovsrol','akhlakh','tsogtsolbor', 'tss',
        'arkhangai', 'dalanzadgad', 'bayan olgii', 'olgii', 'khumuun','iin','in',
    ]
    for w in stop_words:
        n = n.replace(w, '')

    # Илүүдэл зайг цэвэрлэх
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def find_best_match(target_name: str, queryset):
    """
    queryset доторх School-уудын name болон alias бүрийг харьцуулж хамгийн өндөр оноотойг буцаана.
    alias нь таслалаар тусгаарлагдсан олон нэр байж болно.
    """
    best, best_score = None, 0
    n1 = normalize_name(target_name)
    n1_joined = n1.replace(' ', '')

    for s in queryset:
        # name талбар
        name_norm = normalize_name(s.name)
        score_name = max(
            fuzz.token_sort_ratio(n1, name_norm),
            fuzz.ratio(n1_joined, name_norm.replace(' ', ''))
        )

        # alias талбар (олон утгатай)
        score_alias = 0
        if s.alias:
            # таслалаар заагласан бүх алиасыг шалгах
            aliases = [a.strip() for a in s.alias.split(',') if a.strip()]
            for a in aliases:
                a_norm = normalize_name(a)
                score_alias = max(
                    score_alias,
                    fuzz.token_sort_ratio(n1, a_norm),
                    fuzz.ratio(n1_joined, a_norm.replace(' ', ''))
                )

        # name болон alias дундаас хамгийн өндөр оноог сонгох
        score = max(score_name, score_alias)
        if score > best_score:
            best, best_score = s, score

    return best, best_score

def guess_school(user_meta) -> School | None:
    """
    1. province_id >21 (УБ дүүрэг) бол тухайн дүүрэг → УБ бүх дүүрэг → бусад аймаг.
    2. province_id ≤21 (аймаг) бол тухайн аймаг → бусад аймаг.
    """
    if not user_meta.user_school_name:
        return None

    pid = user_meta.province_id
    target_name = user_meta.user_school_name

    # 1-р шат: тухайн province дотор
    qs = School.objects.filter(province_id=pid)
    best, score = find_best_match(target_name, qs)
    if best and score >= 75:
        return best

    if pid and pid > 21:
        # УБ-ийн бүх дүүрэг дотроос хайх
        qs = School.objects.filter(province_id__gt=21)
        best, score = find_best_match(target_name, qs)
        if best and score >= 90:
            return best

    return None

# surguuliin buh burtgeltei suragchdiin surguuliig update hiih
def set_students_school(school_id):
    count = 0
    school = School.objects.get(pk=school_id)
    for user in school.group.user_set.all():
        user.data.school=school
        user.data.save()
        user.is_active=True
        user.data.is_valid=True
        user.save()
        count = count + 1
    return count
