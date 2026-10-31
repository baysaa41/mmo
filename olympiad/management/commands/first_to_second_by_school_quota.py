# olympiad/management/commands/first_to_second_by_school_quota.py
"""
I давааны олимпиадаас II давааны I шат (round=2) руу шалгарах сурагчдыг
сургууль, ангилал тус бүрийн квотын дагуу тодруулна.

Квот нь `olympiad.utils.round2_quota.compute_school_quota_table()`-ийн
"Нийт квот" баганатай ижил (Квотын дэвтэрт харагддаг тоо):

  - "Сургуулиас" (суурь): ангилал бүрд сургууль бүрийн эхний 2 (аймаг) /
    3 (дүүрэг) сурагч.
  - Нэмэлт: сүүлийн 3 жилийн round=2-ын Top 20 (аймаг) / Top 50 (дүүрэг)
    дүнгээс сургууль тус бүрээр ceil(дундаж) байдлаар олгох нэмэлт эрх.
    Энэ нь зөвхөн эрхийн ТООГ тодорхойлно; хэнийг сонгохыг сургуулийн
    дотоод эрэмбээр (I давааны оноогоор) шийднэ.
  - Нийт квот = суурь + нэмэлт.

Сонголт: сургууль бүрд I давааны албан ёсны (`is_official=True`) онооны
хуудсуудыг оноогоор буурахаар эрэмбэлж, нийт квотоор нь эхний сурагчдыг
авна. 0 оноотой сурагч хасагдана (5.8-р заалт). Квотын зааг дээр оноо
тэнцсэн бол анхдагчаар "тэнцвэл цөөнийг сонгоно" дүрмээр тэнцсэн бүхлийг
хасна (`--tie-policy fewer`). `exact` — квотын хэмжээгээр нэрээр эрэмбэлж
авах, `more` — тэнцсэн бүхлийг авах.

"Жагсаалтаар" гэсэн өмнөх жилийн жагсаалтын сонголт байхгүй: квотад
багтсан сурагчдыг бүгдийг тухайн сургуулийн дотоод эрэмбээр (I давааны
оноогоор) сонгоно. Иймд бүх эрх нэг нэртэй — '2.1 эрх сургуулиас'.

Хадгалах үед (--dry-run өгөөгүй бол):
  - I давааны олимпиадад Award(place='2.1 эрх сургуулиас')
  - I давааны ScoreSheet.prizes-д мөн адил тэмдэглэнэ
  - Харгалзах round=2 олимпиадын группт нэмнэ

Жишээ:
  python manage.py first_to_second_by_school_quota --dry-run
  python manage.py first_to_second_by_school_quota --year 63 --dry-run --output selected.xlsx
  python manage.py first_to_second_by_school_quota --year 63
"""
from collections import defaultdict
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from accounts.models import Province
from olympiad.models import Award, Olympiad, ScoreSheet, SchoolYear
from olympiad.utils.group_management import ensure_olympiad_has_group
from olympiad.utils.round2_quota import compute_school_quota_table

PLACE_SCHOOL = '2.1 эрх сургуулиас'
# Өмнөх хувилбарын тэмдэглэгээ — зөвхөн хуучин бичлэгийг цэвэрлэхэд ашиглана.
PLACE_OLD_LIST = '2.1 эрх жагсаалтаар'
OUR_PLACES = (PLACE_SCHOOL, PLACE_OLD_LIST)
CHUNK_SIZE = 500


def select_school_students(rows, quota, tie_policy='fewer'):
    """Нэг сургуулийн сурагчдаас квотын хэмжээгээр сонгоно.

    rows: [{'total': float, 'user_id': int, 'last_name': str, 'first_name': str, ...}, ...]
    quota: тухайн сургууль, ангиллын нийт эрх (суурь + нэмэлт)
    tie_policy:
      'fewer'  — зааг дээр тэнцсэн бүхлийг хасна (анхдагч, удирдамжийн
                 "тэнцвэл цөөнийг сонгоно").
      'exact'  — квотын хэмжээгээр яг авна; тэнцсэн бол нэрээр эрэмбэлнэ.
      'more'   — зааг дээр тэнцсэн бүхлийг авна (квотоос хэтэрч болно).
    """
    rows = sorted(rows, key=lambda r: (
        -r['total'], r.get('last_name') or '', r.get('first_name') or '', r['user_id'],
    ))

    if quota <= 0:
        return []
    if len(rows) <= quota:
        return rows

    cutoff_score = rows[quota - 1]['total']
    boundary_tied = rows[quota]['total'] == cutoff_score
    if not boundary_tied:
        return rows[:quota]

    if tie_policy == 'more':
        return [r for r in rows if r['total'] >= cutoff_score]
    if tie_policy == 'fewer':
        return [r for r in rows if r['total'] > cutoff_score]
    return rows[:quota]


def strip_our_places(prizes):
    """prizes мөрөөс энэ командын тэмдэглэгээг хасна (бусад шагналыг хадгална)."""
    if not prizes:
        return ''
    parts = [p.strip() for p in prizes.split(',') if p.strip() and p.strip() not in OUR_PLACES]
    return ', '.join(parts)


def append_place(prizes, place):
    base = strip_our_places(prizes)
    return f'{base}, {place}' if base else place


def chunked(items, size=CHUNK_SIZE):
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i:i + size]


class Command(BaseCommand):
    help = (
        'I давааны олимпиадаас II давааны I шат (round=2) руу шалгарах сурагчдыг '
        'сургууль, ангилал тус бүрийн квотын дагуу тодруулна. Квот = суурь (2/3) + '
        'нэмэлт (сүүлийн 3 жилийн дундаж); сонголтыг сургуулийн дотоод эрэмбээр хийнэ.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--year', type=int,
            help='SchoolYear ID (анхдагч: өнөөдрийн идэвхтэй хичээлийн жил)',
        )
        parser.add_argument(
            '--round2-olympiad-id', type=int, action='append', dest='round2_ids',
            help='Зөвхөн заасан round=2 олимпиадуудыг боловсруулна (олон удаа өгч болно)',
        )
        parser.add_argument(
            '--tie-policy', choices=('fewer', 'exact', 'more'), default='fewer',
            help='Квотын зааг дээр оноо тэнцсэн үед: fewer=тэнцсэн бүхлийг хасна (анхдагч), '
                 'exact=квотын хэмжээгээр нэрээр эрэмбэлнэ, more=тэнцсэн бүхлийг авна',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Өгөгдөл хадгалахгүй, зөвхөн үр дүнг харуулна.',
        )
        parser.add_argument(
            '--output', type=str,
            help='Сонгогдсон сурагчдын жагсаалтыг Excel (.xlsx) эсвэл CSV (.csv) файлд хадгална.',
        )
        parser.add_argument(
            '--no-group', action='store_true',
            help='Сонгогдсон сурагчдыг round=2 олимпиадын группт нэмэхгүй.',
        )
        parser.add_argument(
            '--prune-groups', action='store_true',
            help='Энэ командын өмнөх ажиллагаагаар группт нэмэгдсэн, одоо сонгогдоогүй '
                 'сурагчдыг round=2 группээс хасна.',
        )

    # ------------------------------------------------------------------ #
    def handle(self, *args, **options):
        year = self._resolve_year(options['year'])
        targets = self._resolve_targets(year, options['round2_ids'])

        if not targets:
            raise CommandError(f'{year.name}: боловсруулах round=2 олимпиад олдсонгүй.')

        self.stdout.write(self.style.HTTP_INFO(
            f'Хичээлийн жил: {year.name} (ID={year.id})'
        ))
        self.stdout.write(f'Квотын эх сурвалж: compute_school_quota_table() — сургууль × ангилал')
        self.stdout.write(f'Тэнцлийн дүрэм: --tie-policy={options["tie_policy"]}')
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('--dry-run: өгөгдөл хадгалахгүй.'))

        selected_rows = []
        summary = []
        processed_targets = []

        for round2 in targets:
            round1_olympiads = list(
                Olympiad.objects.filter(next_round=round2).select_related('level')
            )
            if not round1_olympiads:
                self.stdout.write(self.style.WARNING(
                    f'\n⚠ {round2.name} (ID={round2.id}): холбогдсон round=1 олимпиад '
                    f'байхгүй тул алгаслаа.'
                ))
                continue

            processed_targets.append((round2, [o.id for o in round1_olympiads]))
            level_name = round2.level.name if round2.level else '—'

            self.stdout.write(self.style.HTTP_INFO(
                f'\n{"=" * 78}\n{level_name} | {round2.name} (ID={round2.id})'
                f'\nI даваа: {", ".join(str(o.id) for o in round1_olympiads)}'
                f'\n{"=" * 78}'
            ))

            province_ids = list(
                ScoreSheet.objects.filter(
                    olympiad__in=round1_olympiads,
                    is_official=True,
                    total__gt=0,
                    school__province__isnull=False,
                ).values_list('school__province_id', flat=True).distinct()
            )
            provinces = Province.objects.filter(id__in=province_ids).order_by('name')

            for province in provinces:
                table = compute_school_quota_table(province, round2)
                if not table:
                    continue

                quota_by_school = {}
                base_by_school = {}
                for data in table['schools_data']:
                    school = data['school']
                    if school is None:
                        continue
                    quota_by_school[school.id] = data['total_quota']
                    base_by_school[school.id] = data['base_quota']

                selected, stats = self._select_for_province(
                    round1_olympiads, province, round2, level_name,
                    quota_by_school, base_by_school, options['tie_policy'],
                )
                selected_rows.extend(selected)
                summary.append(stats)

                self.stdout.write(
                    f'  {province.name:<32} оролцогч {stats["participants"]:>6} | '
                    f'квот {stats["quota"]:>5} | сонгогдсон {stats["selected"]:>5} | '
                    f'сургууль {stats["schools"]:>4}'
                    + (f' | зааг дээр тэнцсэн {stats["boundary_tie"]}' if stats['boundary_tie'] else '')
                )

        if not selected_rows:
            self.stdout.write(self.style.WARNING('\nСонгогдсон сурагч байхгүй.'))
            return

        self._print_totals(selected_rows, summary)

        if options['output']:
            self._write_output(options['output'], selected_rows)

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('\n--dry-run: өгөгдөл хадгалагдаагүй.'))
            return

        self._save(selected_rows, processed_targets, options)

    # ------------------------------------------------------------------ #
    def _resolve_year(self, year_id):
        if year_id:
            year = SchoolYear.objects.filter(pk=year_id).first()
            if not year:
                raise CommandError(f'SchoolYear ID={year_id} олдсонгүй.')
            return year

        today = date.today()
        year = SchoolYear.objects.filter(start__lte=today, end__gte=today).first()
        if not year:
            raise CommandError('Идэвхтэй хичээлийн жил олдсонгүй. --year өгнө үү.')
        return year

    def _resolve_targets(self, year, round2_ids):
        if round2_ids:
            targets = Olympiad.objects.filter(id__in=round2_ids).select_related('level')
        else:
            targets = Olympiad.objects.filter(round=2, school_year=year).exclude(
                Q(level__name__startswith='S') | Q(level__name__startswith='T')
            ).select_related('level')
        return list(targets.order_by('level_id', 'id'))

    # ------------------------------------------------------------------ #
    def _select_for_province(self, round1_olympiads, province, round2, level_name,
                             quota_by_school, base_by_school, tie_policy):
        """Тухайн аймаг/дүүргийн сургууль бүрээс квотын дагуу сурагч сонгоно."""
        sheets = ScoreSheet.objects.filter(
            olympiad__in=round1_olympiads,
            school__province=province,
            is_official=True,
            total__gt=0,
        ).select_related('user', 'school').order_by('school_id', '-total', 'user_id')

        # Нэг сурагчийн хэд хэдэн онооны хуудас байвал хамгийн өндрийг нь л авна.
        by_school = defaultdict(dict)  # school_id -> {user_id: best Sheet}
        for sheet in sheets:
            if sheet.school_id is None or sheet.user_id is None:
                continue
            current = by_school[sheet.school_id].get(sheet.user_id)
            if current is None or (sheet.total or 0) > (current.total or 0):
                by_school[sheet.school_id][sheet.user_id] = sheet

        selected = []
        total_quota = 0
        boundary_tie = 0

        for school_id, users in by_school.items():
            base_quota = base_by_school.get(school_id, 0)
            quota = quota_by_school.get(school_id, base_quota)
            total_quota += quota

            rows = [
                {
                    'user_id': user_id,
                    'total': sheet.total or 0,
                    'last_name': sheet.user.last_name if sheet.user else '',
                    'first_name': sheet.user.first_name if sheet.user else '',
                    'scoresheet': sheet,
                    'school': sheet.school,
                    'olympiad_id': sheet.olympiad_id,
                    'round2_id': round2.id,
                    'category': level_name,
                    'province': province,
                    'school_id': school_id,
                    'quota': quota,
                }
                for user_id, sheet in users.items()
            ]

            picked = select_school_students(rows, quota, tie_policy)

            # Квотын зааг дээр тэнцсэн сурагчдын тоо (зөвхөн мэдээлэл).
            all_sorted = sorted(rows, key=lambda r: (
                -r['total'], r.get('last_name') or '', r.get('first_name') or '', r['user_id'],
            ))
            if len(all_sorted) > quota > 0:
                cutoff = all_sorted[quota - 1]['total']
                if all_sorted[quota]['total'] == cutoff:
                    boundary_tie += sum(1 for r in all_sorted if r['total'] == cutoff)

            for index, row in enumerate(picked):
                row['rank_in_school'] = index + 1
                # Бүх эрх сургуулийн дотоод эрэмбээр олгогддог тул нэг нэртэй.
                row['selection_type'] = PLACE_SCHOOL
                selected.append(row)

        stats = {
            'category': level_name,
            'province': province.name,
            'participants': sum(len(v) for v in by_school.values()),
            'quota': total_quota,
            'selected': len(selected),
            'schools': len(by_school),
            'boundary_tie': boundary_tie,
        }
        return selected, stats

    # ------------------------------------------------------------------ #
    def _print_totals(self, selected_rows, summary):
        self.stdout.write(self.style.HTTP_INFO(f'\n{"=" * 78}\nНИЙТ ДҮН\n{"=" * 78}'))

        by_category = defaultdict(lambda: {'quota': 0, 'selected': 0, 'participants': 0})
        for stats in summary:
            entry = by_category[stats['category']]
            entry['quota'] += stats['quota']
            entry['selected'] += stats['selected']
            entry['participants'] += stats['participants']

        for category, entry in by_category.items():
            self.stdout.write(
                f'  {category:<14} оролцогч {entry["participants"]:>7} | '
                f'квот {entry["quota"]:>6} | сонгогдсон {entry["selected"]:>6}'
            )

        total_selected = len(selected_rows)
        self.stdout.write(self.style.SUCCESS(f'\nНийт сонгогдсон: {total_selected}'))

        by_type = defaultdict(int)
        for row in selected_rows:
            by_type[row['selection_type']] += 1
        for place, count in by_type.items():
            self.stdout.write(f'  {place}: {count}')

    # ------------------------------------------------------------------ #
    def _write_output(self, path, selected_rows):
        import pandas as pd

        data = [
            {
                'Ангилал': row['category'],
                'Аймаг/Дүүрэг': row['province'].name,
                'Сургууль': row['school'].name if row['school'] else 'Тодорхойгүй',
                'Овог': row['scoresheet'].user.last_name if row['scoresheet'].user else '',
                'Нэр': row['scoresheet'].user.first_name if row['scoresheet'].user else '',
                'User ID': row['user_id'],
                'Оноо': row['total'],
                'Сургууль доторх байр': row['rank_in_school'],
                'Квот': row['quota'],
                'Эрхийн төрөл': row['selection_type'],
            }
            for row in selected_rows
        ]
        df = pd.DataFrame(data)

        if path.lower().endswith('.csv'):
            df.to_csv(path, index=False, encoding='utf-8-sig')
        else:
            df.to_excel(path, index=False)

        self.stdout.write(self.style.SUCCESS(f'\n💾 {len(data)} мөр хадгалагдлаа: {path}'))

    # ------------------------------------------------------------------ #
    def _save(self, selected_rows, processed_targets, options):
        round1_ids = [oid for _, ids in processed_targets for oid in ids]
        round2_by_id = {round2.id: round2 for round2, _ in processed_targets}

        # Award/prizes-д давхардахгүйн тулд (olympiad, user) хосоор нэгтгэнэ.
        unique_rows = {}
        for row in selected_rows:
            key = (row['olympiad_id'], row['user_id'])
            if key not in unique_rows or row['total'] > unique_rows[key]['total']:
                unique_rows[key] = row
        unique_rows = list(unique_rows.values())

        self.stdout.write('\nӨгөгдөл хадгалж байна...')

        with transaction.atomic():
            # --- Өмнөх энэ командын award-уудыг устгана ---
            old_awards = list(
                Award.objects.filter(olympiad_id__in=round1_ids, place__in=OUR_PLACES)
                .values_list('olympiad_id', 'contestant_id')
            )
            deleted, _ = Award.objects.filter(
                olympiad_id__in=round1_ids, place__in=OUR_PLACES
            ).delete()
            if deleted:
                self.stdout.write(f'  Хуучин {deleted} award устгагдлаа.')

            # --- Шинэ award ---
            Award.objects.bulk_create([
                Award(
                    olympiad_id=row['olympiad_id'],
                    contestant_id=row['user_id'],
                    place=row['selection_type'],
                )
                for row in unique_rows
            ])
            self.stdout.write(self.style.SUCCESS(f'  {len(unique_rows)} award үүсгэгдлээ.'))

            # --- ScoreSheet.prizes ---
            selected_sheet_ids = {row['scoresheet'].id for row in selected_rows}
            stale = ScoreSheet.objects.filter(
                olympiad_id__in=round1_ids
            ).filter(
                Q(prizes__contains=PLACE_SCHOOL) | Q(prizes__contains=PLACE_OLD_LIST)
            )

            to_update = {}
            for sheet in stale:
                if sheet.id in selected_sheet_ids:
                    continue
                cleaned = strip_our_places(sheet.prizes)
                if cleaned != (sheet.prizes or ''):
                    sheet.prizes = cleaned
                    to_update[sheet.id] = sheet

            for row in selected_rows:
                sheet = row['scoresheet']
                sheet.prizes = append_place(sheet.prizes, row['selection_type'])
                to_update[sheet.id] = sheet

            to_update = list(to_update.values())
            ScoreSheet.objects.bulk_update(to_update, ['prizes'], batch_size=1000)
            self.stdout.write(self.style.SUCCESS(
                f'  {len(to_update)} ScoreSheet-ийн prizes шинэчлэгдлээ.'
            ))

            # --- Round=2 групп ---
            users_by_round2 = defaultdict(set)
            for row in selected_rows:
                users_by_round2[row['round2_id']].add(row['user_id'])

            if not options['no_group']:
                added = 0
                for round2_id, user_ids in users_by_round2.items():
                    round2 = round2_by_id[round2_id]
                    group, _ = ensure_olympiad_has_group(round2)
                    for chunk in chunked(user_ids):
                        group.user_set.add(*chunk)
                        added += len(chunk)
                self.stdout.write(self.style.SUCCESS(
                    f'  {added} сурагч round=2 группт нэмэгдлээ.'
                ))

            # --- Хуучин сонгогдсон, одоо сонгогдоогүй сурагчдыг группээс хасах ---
            if options['prune_groups'] and not options['no_group']:
                round1_to_round2 = {
                    oid: round2.id for round2, ids in processed_targets for oid in ids
                }
                previous_by_round2 = defaultdict(set)
                for olympiad_id, contestant_id in old_awards:
                    target_id = round1_to_round2.get(olympiad_id)
                    if target_id:
                        previous_by_round2[target_id].add(contestant_id)

                removed = 0
                for round2_id, previous_ids in previous_by_round2.items():
                    stale_ids = previous_ids - users_by_round2.get(round2_id, set())
                    if not stale_ids:
                        continue
                    round2 = round2_by_id[round2_id]
                    group, _ = ensure_olympiad_has_group(round2)
                    for chunk in chunked(stale_ids):
                        group.user_set.remove(*chunk)
                        removed += len(chunk)
                if removed:
                    self.stdout.write(self.style.SUCCESS(
                        f'  {removed} хуучин сурагч группээс хасагдлаа.'
                    ))

        self.stdout.write(self.style.SUCCESS('\n✓ Амжилттай дууслаа!'))
