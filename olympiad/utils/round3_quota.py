"""
Нийслэлийн олимпиад (round=3, "Хотын эрх"): дүүрэг тус бүрийн эрхийн тооцоо.

6.5-р заалтын дагуу:
  - "Хотын эрх, дүүргээс" (суурь): сурагчдын ангилал бүрд дүүрэг бүрийн эхний 20,
    багш нарын ангилал бүрд дүүрэг бүрийн эхний 10 байр нийслэлийн олимпиадад орно.
  - "Хотын эрх, жагсаалтаар" (нэмэлт эрх):
      Сурагчид: тухайн дүүргийн сурагчдаас сүүлийн 3 жилд нийслэлийн олимпиадад
        эхний 30 байрт шалгарсан сурагчдын дундаж тоог дээш нь бүхэлчилж тооцно
        (round2_quota.py-ийн "ОДООГИЙН" аргатай адил, зөвхөн дүүргийн түвшинд).
      Багш нар: тухайн дүүргийн багш нараас сүүлийн 3 жилд нийслэлийн олимпиадад
        эхний 10 байрт шалгарсан тоог үндэслэн, ангилал бүрд нийт 10 эрхийг A/B
        харьцаагаар 7 дүүрэгт хуваарилна (round2_quota.py-ийн "ШИНЭ" A/B аргатай
        адил).

Нийслэлийн 7 дүүргийг Province.zone (Zone id == 5, 'Улаанбаатар') FK-аар тодорхойлно.

Тухайн жилийн round=3 олимпиад ангилал бүрд 1 (хуучин, нийслэл/бүс хамт) эсвэл 2
(2024-2025-аас хойш: "нийслэл" ба "бүс" тусдаа) объекттой байж болно.

ЧУХАЛ: "нийслэл" олимпиадын гишүүнчлэл (аль объектод бүртгэлтэй байгаа нь) ӨӨРӨӨ
"жинхэнэ УБ хотын сурагч" гэсэн үг БИШ. "Нийслэл" олимпиадыг тусад нь салгасан
шалтгаан нь өөр — зөвхөн улсын квотод (round=3 → round=4, Улсын эрх) өрсөлдөхөөр
нийслэлд ирсэн БУСАД аймгийн сурагчдыг өөрийн аймгийн жагсаалтад биш нийслэлийн
жагсаалтад жагсаах зорилготой (энэ логикийг third_to_fourth_by_ranking.py тусад нь
хэрэгжүүлдэг). Иймд энэ модулийн зорилго (7 ДҮҮРЭГ тус бүрийн "жагсаалтаар" квот) —д
"нийслэл" объектын гишүүнчлэлд итгэж болохгүй: тэр объект жинхэнэ бус, зөвхөн
дамжин өрсөлдсөн (аймгийн сургуультай) сурагч агуулж болзошгүй.

Тиймээс round=3-ийн БҮХ объектыг (нийслэл + бүс) нэгтгээд, тэднээс аль хэдийн
тооцогдсон `ranking_b_z` талбарыг ашиглана (ranking.py: update_rankings_b_z,
"тэнцвэл цөөнийг сонгоно" дүрмээр тооцогддог тул дахин тооцох шаардлагагүй) —
ГЭХДЭЭ уг талбар олимпиадад ОРШИХ БҮХ зон (1-5) бүрд тус тусад нь тооцогддог тул
ЗААВАЛ `school__province__zone_id=CAPITAL_ZONE_ID` шүүлттэй ХАМТ хэрэглэнэ (доор,
round3_topn_by_district-ийн тайлбарыг үз). Нэг сурагч хоёр round=3 олимпиадад
зэрэг бүртгэлтэй байдаггүй тул нэгтгэхэд давхардал үүсэхгүй.
"""
import math

from olympiad.models import Olympiad, ScoreSheet, SchoolYear
from accounts.models import Province

CAPITAL_ZONE_ID = 5  # Zone 'Улаанбаатар'


def get_capital_districts():
    """Нийслэлийн 7 дүүргийг буцаана (Zone id=5, 'Улаанбаатар')."""
    return Province.objects.filter(zone_id=CAPITAL_ZONE_ID).order_by('name')


def get_round3_olympiads(level, school_year_id):
    """Тухайн ангилал, хичээлийн жилийн БҮХ round=3 олимпиадуудыг буцаана (нийслэл +
    бүс хоёул, эсвэл хуучин форматад ганц хосолсон олимпиад)."""
    return list(Olympiad.objects.filter(round=3, school_year_id=school_year_id, level=level))


def get_capital_round3_olympiad(level, school_year_id):
    """Тухайн ангилал, хичээлийн жилийн нийслэлд зориулсан round=3 олимпиадыг олно
    (харуулах/холбоос зориулалттай — нэрэндээ "нийслэл" гэсэн үгтэй объект байвал
    түүнийг, эс бөгөөс round=3-ийн эхний объектыг буцаана)."""
    named = Olympiad.objects.filter(
        round=3, school_year_id=school_year_id, level=level, name__icontains='нийслэл'
    ).first()
    if named:
        return named
    return Olympiad.objects.filter(round=3, school_year_id=school_year_id, level=level).first()


def round3_topn_by_district(round3_olympiads, quota_n):
    """Тухайн (өнгөрсөн жилийн) round=3-ийн БҮХ олимпиадаас (нийслэл + бүс, эсвэл
    хуучин ганц хосолсон) аль хэдийн тооцогдсон `ranking_b_z` талбарыг ашиглаж,
    зөвхөн нийслэлийн дүүргийн (zone_id=5) Top N-д орсныг дүүргээр бүлэглэж тоолно.

    `ranking_b_z` нь ЗОНЫ ДОТООД байр — ranking.py-ийн update_rankings_b_z(olympiad_id,
    zone_id) олимпиадад ОРШИХ БҮХ зоны хувьд (1-5) тус тусад нь дуудагддаг тул нэг
    ScoreSheet-ийн ranking_b_z нь зөвхөн ӨӨРИЙН зон дотор хэддүгээрт орсныг заана —
    өөр зоны 1-10-т орсон хүмүүс ч мөн адил ranking_b_z=1..10 утгатай байдаг. Тиймээс
    `ranking_b_z<=quota_n` шүүлтийг ЗААВАЛ `school__province__zone_id=CAPITAL_ZONE_ID`
    шүүлттэй хамт хэрэглэнэ ("тэнцвэл цөөнийг сонгоно" дүрмийг дахин тооцох
    шаардлагагүй болгохын тулд л ranking_b_z-г ашигладаг, зоныг тодорхойлдогт биш).

    Нэг сурагч хоёр round=3 олимпиадад зэрэг бүртгэлтэй байдаггүй тул олимпиадуудыг
    нэгтгэхэд давхардал үүсэхгүй.
    """
    if not round3_olympiads:
        return {}

    qualified = ScoreSheet.objects.filter(
        olympiad__in=round3_olympiads,
        total__gt=0,
        school__province__zone_id=CAPITAL_ZONE_ID,
        ranking_b_z__gte=1,
        ranking_b_z__lte=quota_n,
    ).values_list('school__province_id', flat=True)

    counts = {}
    for province_id in qualified:
        if province_id is None:
            continue
        counts[province_id] = counts.get(province_id, 0) + 1
    return counts


def round3_avg_quota_by_district(level, year_ids, quota_n):
    """Сурагчид: сүүлийн 3 жилийн Top N тоог дүүрэг тус бүрээр дундажлаад дээш нь
    бүхэлчилнэ (ceil(avg)) — round2_avg_quota_by_school-тэй адил арга, дүүргийн түвшинд.

    Буцаана: per_district: dict {province_id: {'yearly_counts': [...], 'additional_quota': int}}
    """
    yearly_counts_list = []
    for yid in year_ids:
        hist_olympiads = get_round3_olympiads(level, yid)
        counts = round3_topn_by_district(hist_olympiads, quota_n)
        yearly_counts_list.append(counts)

    all_district_ids = set()
    for counts in yearly_counts_list:
        all_district_ids.update(counts.keys())

    per_district = {}
    for district_id in all_district_ids:
        yearly = [counts.get(district_id, 0) for counts in yearly_counts_list]
        per_district[district_id] = {
            'yearly_counts': yearly,
            'additional_quota': math.ceil(sum(yearly) / 3),
        }
    return per_district


def round3_ratio_quota_by_district(level, year_ids, quota_n, total_quota):
    """Багш нар: тогтмол нийт эрхийг (жиш нь 10) A/B харьцаагаар 7 дүүрэгт хуваарилна.

    A(дүүрэг) = тухайн дүүргээс 3 жилд Top N-д орсон нийт багшийн тоо.
    B = нийслэл даяар 3 жилд Top N-д орсон нийт багшийн тоо.
    Нэмэлт эрх(дүүрэг) = ceil((A / B) * total_quota).

    Буцаана: (per_district, total_B)
    """
    yearly_counts_list = []
    total_b = 0
    for yid in year_ids:
        hist_olympiads = get_round3_olympiads(level, yid)
        counts = round3_topn_by_district(hist_olympiads, quota_n)
        yearly_counts_list.append(counts)
        total_b += sum(counts.values())

    all_district_ids = set()
    for counts in yearly_counts_list:
        all_district_ids.update(counts.keys())

    per_district = {}
    for district_id in all_district_ids:
        yearly = [counts.get(district_id, 0) for counts in yearly_counts_list]
        total_a = sum(yearly)
        additional_quota = math.ceil((total_a / total_b) * total_quota) if total_b > 0 else 0
        per_district[district_id] = {
            'yearly_counts': yearly,
            'total_A': total_a,
            'additional_quota': additional_quota,
        }
    return per_district, total_b


def compute_district_quota_table(level, school_year, is_teacher_category,
                                  base_quota_per_district=None, historical_topn=None,
                                  teacher_total_quota=10):
    """Тухайн ангилал, хичээлийн жилийн хувьд нийслэлийн 7 дүүрэг тус бүрийн round=3
    эрхийн хүснэгтийг бүрэн тооцоолж буцаана.

    Сурагчийн ангилалд (`is_teacher_category=False`) суурь = 20, "жагсаалтаар" нэмэлт
    эрхийг дүүрэг тус бүрээр тусад нь дундаж-суурьт аргаар Top 30-аар тооцно (нийлбэр
    хязгааргүй).

    Багшийн ангилалд (`is_teacher_category=True`) суурь = 10, "жагсаалтаар" нэмэлт эрх
    нь тогтмол нийт {teacher_total_quota}-г Top 10-аар тооцсон A/B харьцаагаар
    дүүргүүдэд хуваарилна.

    Хэрэв энэ жилийн нийслэлийн round=3 олимпиад олдохгүй бол None буцаана.
    """
    round3_olympiad = get_capital_round3_olympiad(level, school_year.id)
    if round3_olympiad is None:
        return None

    if base_quota_per_district is None:
        base_quota_per_district = 10 if is_teacher_category else 20

    if historical_topn is None:
        historical_topn = 10 if is_teacher_category else 30

    districts = list(get_capital_districts())

    year_ids = [school_year.id - d for d in (3, 2, 1)]
    year_names = []
    year_olympiad_ids = []
    year_is_combined = []
    for yid in year_ids:
        sy = SchoolYear.objects.filter(id=yid).first()
        year_names.append(sy.name if sy else '—')
        hist_olympiads = get_round3_olympiads(level, yid)
        anchor = get_capital_round3_olympiad(level, yid)
        year_olympiad_ids.append(anchor.id if anchor else None)
        year_is_combined.append(len(hist_olympiads) <= 1)

    total_b = None
    if is_teacher_category:
        per_district, total_b = round3_ratio_quota_by_district(
            level, year_ids, historical_topn, teacher_total_quota
        )
    else:
        per_district = round3_avg_quota_by_district(level, year_ids, historical_topn)

    districts_data = []
    for district in districts:
        info = per_district.get(district.id, {'yearly_counts': [0, 0, 0], 'additional_quota': 0})
        row = {
            'district': district,
            'base_quota': base_quota_per_district,
            'yearly_counts': info['yearly_counts'],
            'additional_quota': info['additional_quota'],
        }
        row['total_quota'] = row['base_quota'] + row['additional_quota']
        districts_data.append(row)

    districts_data.sort(key=lambda d: (-d['total_quota'], d['district'].name))

    return {
        'round3_olympiad': round3_olympiad,
        'is_teacher_category': is_teacher_category,
        'base_quota_per_district': base_quota_per_district,
        'historical_topn': historical_topn,
        'teacher_total_quota': teacher_total_quota,
        'total_B': total_b,
        'year_ids': year_ids,
        'year_names': year_names,
        'year_olympiad_ids': year_olympiad_ids,
        'year_columns': [
            {'name': name, 'olympiad_id': oid, 'is_combined': combined}
            for name, oid, combined in zip(year_names, year_olympiad_ids, year_is_combined)
        ],
        'districts_data': districts_data,
        'total_base': sum(d['base_quota'] for d in districts_data),
        'total_yearly_counts': [sum(d['yearly_counts'][i] for d in districts_data) for i in range(3)],
        'total_additional': sum(d['additional_quota'] for d in districts_data),
        'total_quota': sum(d['total_quota'] for d in districts_data),
    }
