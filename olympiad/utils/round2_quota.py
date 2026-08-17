"""
2-р давааны (аймаг/дүүргийн олимпиад) сургууль тус бүрийн эрхийн тооцоо.

I давааны шинэ зааврын дагуу (2026 оны 4 сарын 22-ны удирдамж, 5.7-р заалт):
  - "Сургуулиас": ангилал бүрд сургууль бүрийн эхний 2 (аймаг) / 3 (дүүрэг) сурагч.
  - "Жагсаалтаар" (нэмэлт эрх): round=2 олимпиадад сүүлийн 3 жилд тухайн сургуулиас
    Top 20/50-д орсон сурагчдын тоог үндэслэнэ.

Одоогоор аль аргыг ашиглахаа шийдээгүй тул ХОЁУЛАНГ нь тооцож хадгална:
  - ОДООГИЙН (үндсэн) арга: 3 жилийн тоог дундажлаад дээш нь бүхэлчилнэ (ceil(avg)).
    Эрэмбэ, тэнцлийг `ranking_b_p` талбараар тооцно (тэнцсэн бүлэг өөрийн бүлгийн
    ХАМГИЙН МУУ байраар тэмдэглэгдэх тул "тэнцвэл цөөнийг сонгоно" гэсэн дүрмийг
    байгалиараа хэрэгжүүлдэг).
  - ШИНЭ (харьцуулах) арга: A/B харьцаагаар тооцно — A = тухайн сургуулиас Top N-д
    орсон нийт тоо (3 жилийн нийлбэр), B = аймаг/дүүрэг даяар Top N-д орсон нийт тоо,
    нэмэлт эрх = ceil((A/B) * N). Эрэмбэ, тэнцлийг `ranking_b_p` талбараар тооцно
    (тэнцсэн бүлэг өөрийн бүлгийн ХАМГИЙН МУУ байраар тэмдэглэгддэг тул "тэнцвэл
    цөөнийг сонгоно" дүрмийг байгалиараа хэрэгжүүлдэг — ОДООГИЙН аргатай адил).
"""
import math
from itertools import groupby

from olympiad.models import Olympiad, ScoreSheet, SchoolYear


def round2_topn_by_school(round2_olympiad, province, quota_n, rank_field='ranking_a_p'):
    """Тухайн round=2 олимпиадад энэ аймаг/дүүргийн Top N (жагсаалтаар шалгарсан) сурагчдыг
    сургуулиар бүлэглэж тоолно: `rank_field` (`ranking_a_p` эсвэл `ranking_b_p`) нь 1-ээс
    `quota_n` хүртэл (хамт) байгаа бүх сурагчийг тоолно.

    `ranking_a_p` — тэнцсэн бүлэг өөрийн бүлгийн хамгийн сайн (бага) байраар тэмдэглэгдэнэ
    (стандарт тэмцээний эрэмбэ, жиш: 1,2,2,4) — "уужуу", илүү олон сурагч багтана.
    `ranking_b_p` — тэнцсэн бүлэг өөрийн бүлгийн хамгийн муу (их) байраар тэмдэглэгдэнэ
    (жиш: 1,3,3,4) — "хатуу", "тэнцвэл цөөнийг сонгоно" дүрмийг байгалиараа хэрэгжүүлнэ.

    round=1-ээс ялгаатай нь, round=2 ба түүнээс дээш шатанд бүх ScoreSheet-ийг official
    гэж үзнэ (generate_scoresheets командын дүрэмтэй нийцүүлэв, учир нь is_official
    талбарыг зөвхөн round=1 дээр сургуулийн зөвшөөрөгдсөн түвшингээр шүүхэд ашигладаг).
    Сургуулийн харьяалал нь ScoreSheet.school.province-оор тодорхойлогдоно (сурагчийн
    одоогийн профайл дахь аймаг биш) — өөрчлөгдсөн профайлаас үл хамааран тухайн үеийн
    бодит сургуулиар."""
    filter_kwargs = {
        'olympiad': round2_olympiad,
        'school__province': province,
        'total__gt': 0,
        f'{rank_field}__gte': 1,
        f'{rank_field}__lte': quota_n,
    }
    qualified = ScoreSheet.objects.filter(**filter_kwargs).values_list('school_id', flat=True)

    counts = {}
    for school_id in qualified:
        counts[school_id] = counts.get(school_id, 0) + 1
    return counts


def round2_avg_quota_by_school(province, level, year_ids, quota_n):
    """ОДООГИЙН (үндсэн) арга: сүүлийн 3 жилийн (`year_ids`, SchoolYear ID) round=2 Top N
    (`ranking_b_p` талбараар) тоог сургууль тус бүрээр дундажлаад дээш нь бүхэлчилнэ.

    Нэмэлт эрх(сургууль) = ceil(дундаж(3 жилийн тоо)).

    Буцаана: per_school: dict {school_id: {'yearly_counts': [...], 'additional_quota': int}}
    """
    yearly_counts_list = []
    for yid in year_ids:
        hist_olympiad = Olympiad.objects.filter(round=2, school_year_id=yid, level=level).first()
        counts = round2_topn_by_school(hist_olympiad, province, quota_n, rank_field='ranking_b_p') if hist_olympiad else {}
        yearly_counts_list.append(counts)

    all_school_ids = set()
    for counts in yearly_counts_list:
        all_school_ids.update(counts.keys())

    per_school = {}
    for school_id in all_school_ids:
        yearly = [counts.get(school_id, 0) for counts in yearly_counts_list]
        additional_quota = math.ceil(sum(yearly) / 3)
        per_school[school_id] = {
            'yearly_counts': yearly,
            'additional_quota': additional_quota,
        }

    return per_school


def round2_additional_quota_by_school(province, level, year_ids, quota_n):
    """ШИНЭ (харьцуулах) арга: "жагсаалтаар" нэмэлт эрхийг сүүлийн 3 жилийн (`year_ids`,
    SchoolYear ID) round=2 дүнгээс A/B харьцаагаар (`ranking_b_p` талбараар) тооцно.

    A(сургууль) = тухайн сургуулиас 3 жилд Top N-д орсон нийт сурагчийн тоо.
    B = аймаг/дүүрэг даяар 3 жилд Top N-д орсон нийт сурагчийн тоо (бүх сургуулийн нийлбэр).
    Нэмэлт эрх(сургууль) = ceil((A / B) * quota_n).

    Буцаана:
      per_school: dict {school_id: {'yearly_counts': [...], 'total_A': int, 'additional_quota': int}}
      total_B: int
    """
    yearly_counts_list = []  # жил бүрийн {school_id: тоо}
    total_B = 0
    for yid in year_ids:
        hist_olympiad = Olympiad.objects.filter(round=2, school_year_id=yid, level=level).first()
        counts = round2_topn_by_school(hist_olympiad, province, quota_n, rank_field='ranking_b_p') if hist_olympiad else {}
        yearly_counts_list.append(counts)
        total_B += sum(counts.values())

    all_school_ids = set()
    for counts in yearly_counts_list:
        all_school_ids.update(counts.keys())

    per_school = {}
    for school_id in all_school_ids:
        yearly = [counts.get(school_id, 0) for counts in yearly_counts_list]
        total_a = sum(yearly)
        additional_quota = math.ceil((total_a / total_B) * quota_n) if total_B > 0 else 0
        per_school[school_id] = {
            'yearly_counts': yearly,
            'total_A': total_a,
            'additional_quota': additional_quota,
        }

    return per_school, total_B


def compute_school_quota_table(province, round2_olympiad):
    """Тухайн аймаг/дүүрэг, round=2 (аймаг/дүүргийн олимпиад) олимпиадын хувьд сургууль
    тус бүрийн 2-р даваанд оролцох эрхийн хүснэгтийг бүрэн тооцоолж буцаана.

    Үндсэн (харуулах) дүн нь ОДООГИЙН арга (дундаж-суурьт, ranking_b_p) — "new_" угтвартай
    талбарууд нь ШИНЭ, шийдэгдээгүй A/B харьцаат аргын (мөн ranking_b_p) харьцуулах дүн.

    Хэрэв энэ round2_olympiad-д холбогдсон round=1 олимпиад олдохгүй бол None буцаана
    (тухайлбал, I даваа энэ жил хараахан бэлдэгдээгүй бол)."""
    from schools.models import School

    round1_olympiads = Olympiad.objects.filter(next_round=round2_olympiad)
    if not round1_olympiads.exists():
        return None

    is_aimag = province.id <= 21
    region_type = 'Аймаг' if is_aimag else 'Дүүрэг'
    base_quota_per_school = 2 if is_aimag else 3
    historical_topn = 20 if is_aimag else 50

    # --- 1) СУРГУУЛИАС: аймаг/дүүргийн бүх сургууль стандарт суурь эрхтэй (2 эсвэл 3) ---
    schools_map = {
        school.id: {
            'school': school,
            'round1_participants': 0,
            'base_quota': base_quota_per_school,
            'yearly_counts': [],
        }
        for school in School.objects.filter(province=province)
    }

    round1_scoresheets = list(
        ScoreSheet.objects.filter(
            olympiad__in=round1_olympiads,
            school__province=province,
            is_official=True,
            total__gt=0,
        ).select_related('school').order_by('school_id', '-total', 'user__last_name', 'user__first_name')
    )
    for school_id, group in groupby(round1_scoresheets, key=lambda ss: ss.school_id):
        group = list(group)
        if school_id not in schools_map:
            schools_map[school_id] = {
                'school': group[0].school,
                'round1_participants': 0,
                'base_quota': base_quota_per_school,
                'yearly_counts': [],
            }
        schools_map[school_id]['round1_participants'] = len(group)

    # --- 2) ЖАГСААЛТААР: сүүлийн 3 жилийн round=2 Top N-д хэдэн сурагч оржээ (2 аргаар) ---
    year_ids = [round2_olympiad.school_year_id - d for d in (3, 2, 1)]
    year_names = []
    year_olympiad_ids = []
    for yid in year_ids:
        sy = SchoolYear.objects.filter(id=yid).first()
        year_names.append(sy.name if sy else '—')
        hist_olympiad = Olympiad.objects.filter(round=2, school_year_id=yid, level=round2_olympiad.level).first()
        year_olympiad_ids.append(hist_olympiad.id if hist_olympiad else None)

    avg_by_school = round2_avg_quota_by_school(
        province, round2_olympiad.level, year_ids, historical_topn
    )
    ratio_by_school, total_B = round2_additional_quota_by_school(
        province, round2_olympiad.level, year_ids, historical_topn
    )

    for school_id in set(avg_by_school) | set(ratio_by_school):
        if school_id not in schools_map:
            schools_map[school_id] = {
                'school': School.objects.filter(id=school_id).first() if school_id else None,
                'round1_participants': 0,
                'base_quota': base_quota_per_school,
                'yearly_counts': [],
            }

    # --- 3) Нэгтгэх (одоогийн арга = үндсэн, шинэ арга = харьцуулах) ---
    for school_id, data in schools_map.items():
        avg_info = avg_by_school.get(school_id, {'yearly_counts': [0, 0, 0], 'additional_quota': 0})
        data['yearly_counts'] = avg_info['yearly_counts']
        data['additional_quota'] = avg_info['additional_quota']
        data['total_quota'] = data['base_quota'] + data['additional_quota']

        ratio_info = ratio_by_school.get(school_id, {'yearly_counts': [0, 0, 0], 'total_A': 0, 'additional_quota': 0})
        data['new_yearly_counts'] = ratio_info['yearly_counts']
        data['new_total_A'] = ratio_info['total_A']
        data['new_additional_quota'] = ratio_info['additional_quota']
        data['new_total_quota'] = data['base_quota'] + data['new_additional_quota']

    schools_data = sorted(
        schools_map.values(),
        key=lambda d: (-d['total_quota'], d['school'].name if d['school'] else 'Тодорхойгүй')
    )

    return {
        'round1_olympiads': round1_olympiads,
        'base_quota_per_school': base_quota_per_school,
        'historical_topn': historical_topn,
        'region_type': region_type,
        'year_ids': year_ids,
        'year_names': year_names,
        'year_olympiad_ids': year_olympiad_ids,
        'year_columns': [
            {'name': name, 'olympiad_id': oid}
            for name, oid in zip(year_names, year_olympiad_ids)
        ],
        'total_B': total_B,
        'schools_data': schools_data,
        'total_round1_participants': sum(d['round1_participants'] for d in schools_data),
        'total_base': sum(d['base_quota'] for d in schools_data),
        'total_yearly_counts': [sum(d['yearly_counts'][i] for d in schools_data) for i in range(3)],
        'total_additional': sum(d['additional_quota'] for d in schools_data),
        'total_quota': sum(d['total_quota'] for d in schools_data),
        'total_new_A_sum': sum(d['new_total_A'] for d in schools_data),
        'total_new_additional': sum(d['new_additional_quota'] for d in schools_data),
        'total_new_quota': sum(d['new_total_quota'] for d in schools_data),
    }
