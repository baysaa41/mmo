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

    # ЕБ-ын / ЕБ-ийн / ЕБ-ийнх зэрэг бүх хэлбэрийг арилгах
    n = re.sub(r'\beb[- ]?(iin|iinx|yn|in)?\b', '', n)

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
        '.',',','school','surguuli','surguul','sumin','aimgin','sum','aimag','ebs','eb','in','arvaikheer','buren','dund',
        'laboratori','laboratoroi','neremjit','ulsiin','terguunii','eronkhii','bolovsrol','akhlakh','tsogtsolbor', 'tss',
        'arkhangai', 'dalanzadgad', 'bayan olgii', 'olgii', 'khumuun'
    ]
    for w in stop_words:
        n = n.replace(w, '')

    # Илүүдэл зайг цэвэрлэх
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def find_best_match(target_name: str, queryset):
    best, best_score = None, 0
    n1 = normalize_name(target_name)
    for s in queryset:
        n2 = normalize_name(s.name)
        score = fuzz.token_sort_ratio(n1, n2)
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
