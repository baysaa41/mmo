"""
Хичээлийн жилийн эхэнд сурагчдын ангийг нэгээр ахиулж, 12-р ангийнхныг төгсгөнө.

Хичээлийн жилд НЭГ Л удаа ажиллах ёстой — хоёр удаа ажиллуулбал анги хоёр ахина. Иймд:
  - ажилласан бүрийг logs/advance_grades.log-д (JSON мөр) бичнэ, тухайн жилд бичлэг байвал татгалзана;
  - лог байхгүй ч өмнөх жилийн I давааны оролцогчдын одоогийн ангиас аль хэдийн ахиулсан
    эсэхийг тодорхойлж, ахиулсан бол татгалзана.

    python manage.py advance_grades --check     # юу ч өөрчлөхгүй, төлөвийг харуулна
    python manage.py advance_grades             # ахиулна (баталгаажуулалт асууна)
"""
import getpass
import json
import os
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import UserMeta
from olympiad.models import Olympiad, ScoreSheet, SchoolYear

GRADUATING_GRADE_ID = 12
NEW_GRADE_ID_FOR_GRADUATES = 17
NEW_LEVEL_ID_FOR_GRADUATES = 8
NEW_LEVEL_FOR_GRADE = {
    3: 1, 4: 1,
    5: 2, 6: 2,
    7: 3, 8: 3,
    9: 4, 10: 4,
    11: 5, 12: 5,
}
# Өмнөх жилийн оролцогчдын энэ хувиас илүү нь ангиллынхаа дээд ангиас дээш шилжсэн бол ахиулсан гэж үзнэ
ALREADY_ADVANCED_SHARE = 0.25


def log_path():
    return os.path.join(settings.BASE_DIR, 'logs', 'advance_grades.log')


def read_log():
    try:
        with open(log_path(), encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def write_log(entry):
    os.makedirs(os.path.dirname(log_path()), exist_ok=True)
    with open(log_path(), 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def current_school_year():
    today = timezone.localdate()
    return SchoolYear.objects.filter(start__lte=today, end__gte=today).first()


def detect_already_advanced(school_year):
    """
    Өмнөх хичээлийн жилийн I давааны оролцогчдын хэд нь ангиллынхаа дээд ангиас (жишээ нь C (5-6) → 6)
    дээш шилжсэнийг тооцно. (хувь, тайлбар) буцаана; өмнөх жилийн өгөгдөл байхгүй бол (None, ...).
    """
    prev = SchoolYear.objects.filter(end__lt=school_year.start).order_by('-end').first() if school_year else None
    if not prev:
        return None, 'өмнөх хичээлийн жил олдсонгүй'
    moved = total = 0
    details = []
    for o in Olympiad.objects.filter(school_year=prev, round=1).select_related('level'):
        grades = [int(g) for g in re.findall(r'\d+', o.level.name if o.level else '')]
        if not grades:
            continue
        top = max(grades)
        uids = ScoreSheet.objects.filter(olympiad=o).values_list('user_id', flat=True)
        current = list(UserMeta.objects.filter(user_id__in=uids, grade_id__isnull=False).values_list('grade_id', flat=True))
        above = sum(1 for g in current if g > top)  # 17 (төгссөн) мөн тооцогдоно
        moved += above
        total += len(current)
        details.append(f'{o.level.name}: {above}/{len(current)}')
    if not total:
        return None, f'{prev} — I давааны оролцогч олдсонгүй'
    return moved / total, f'{prev} I давааны оролцогчдоос ангиллынхаа дээд ангиас дээш шилжсэн: ' + ', '.join(details)


class Command(BaseCommand):
    help = 'Сурагчдын анги, ангиллыг шинэчилж, төгсөгчдийн үүргийг тохируулна (хичээлийн жилд нэг удаа).'

    def add_arguments(self, parser):
        parser.add_argument('--check', action='store_true', help='Юу ч өөрчлөхгүй, энэ жил ахиулсан эсэхийг харуулна')
        parser.add_argument('--yes', action='store_true', help='Баталгаажуулалт асуухгүй')
        parser.add_argument('--force', action='store_true',
                            help='Энэ жил ахиулсан гэж тодорхойлогдсон ч ажиллуулна (маш болгоомжтой!)')
        parser.add_argument('--mark-done', metavar='ТАЙЛБАР',
                            help='Ахиулалтыг хийхгүйгээр энэ жилд хийгдсэн гэж логт бүртгэнэ (лог үүсэхээс өмнө ажилласан бол)')

    def handle(self, *args, **opts):
        school_year = current_school_year()
        if not school_year:
            raise CommandError('Өнөөдрийг агуулсан хичээлийн жил олдсонгүй.')

        logged = [e for e in read_log() if e.get('school_year_id') == school_year.id]
        share, detail = detect_already_advanced(school_year)

        self.stdout.write(f'Хичээлийн жил: {school_year}')
        for e in logged:
            self.stdout.write(self.style.WARNING(
                f'  Логт: {e["time"]} — {e.get("action", "advanced")} ({e.get("user", "?")}) {e.get("note", "")}'))
        self.stdout.write(f'  {detail}')
        if share is not None:
            self.stdout.write(f'  → {share:.0%} нь ахисан байна (босго {ALREADY_ADVANCED_SHARE:.0%})')

        already = bool(logged) or (share is not None and share > ALREADY_ADVANCED_SHARE)

        if opts['mark_done']:
            if logged:
                self.stdout.write('Энэ жилд аль хэдийн логт бүртгэгдсэн.')
                return
            write_log({'school_year_id': school_year.id, 'school_year': str(school_year),
                       'time': timezone.localtime().isoformat(timespec='seconds'), 'user': getpass.getuser(),
                       'action': 'marked_done', 'note': opts['mark_done']})
            self.stdout.write(self.style.SUCCESS(f'Энэ жилд хийгдсэн гэж бүртгэлээ: {log_path()}'))
            return

        if opts['check']:
            if already:
                self.stdout.write(self.style.SUCCESS('Энэ хичээлийн жилд анги АЛЬ ХЭДИЙН ахиулсан. Дахин ажиллуулахгүй.'))
            else:
                self.stdout.write(self.style.WARNING('Энэ хичээлийн жилд анги ахиулаагүй бололтой.'))
            return

        if already and not opts['force']:
            raise CommandError('Энэ хичээлийн жилд анги аль хэдийн ахиулсан. Дахин ажиллуулбал анги хоёр ахина. '
                               '(--force-оор албадаж болно, гэхдээ шалтгааныг сайн шалгана уу)')

        if not opts['yes']:
            confirm = input('Та мэдээллийн сангийн нөөц (backup) хийсэн үү? Үргэлжлүүлэх үү? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Үйлдэл цуцлагдлаа.'))
                return

        advanced = {}
        with transaction.atomic():
            # 1. Эхлээд 12-р ангийнхныг төгсгөнө (эс бөгөөс 11 → 12 болсныг төгсгөчихнө)
            graduated = UserMeta.objects.filter(grade_id=GRADUATING_GRADE_ID).update(
                grade_id=NEW_GRADE_ID_FOR_GRADUATES, level_id=NEW_LEVEL_ID_FOR_GRADUATES)
            if graduated:
                self.stdout.write(f'- {GRADUATING_GRADE_ID}-р ангийн {graduated} сурагч төгсөв '
                                  f'(grade_id={NEW_GRADE_ID_FOR_GRADUATES}, level_id={NEW_LEVEL_ID_FOR_GRADUATES})')

            # 2. Дараа нь 11-ээс 1 хүртэл ухрааж ахиулна
            for old_grade_id in range(11, 0, -1):
                new_grade_id = old_grade_id + 1
                update = {'grade_id': new_grade_id}
                if NEW_LEVEL_FOR_GRADE.get(new_grade_id):
                    update['level_id'] = NEW_LEVEL_FOR_GRADE[new_grade_id]
                count = UserMeta.objects.filter(grade_id=old_grade_id).update(**update)
                if count:
                    advanced[str(old_grade_id)] = count
                    self.stdout.write(f'- {old_grade_id}-р ангийн {count} сурагч {new_grade_id}-р анги боллоо.')

            write_log({'school_year_id': school_year.id, 'school_year': str(school_year),
                       'time': timezone.localtime().isoformat(timespec='seconds'), 'user': getpass.getuser(),
                       'action': 'advanced', 'graduated': graduated, 'advanced': advanced,
                       'forced': bool(already and opts['force'])})

        self.stdout.write(self.style.SUCCESS('--- ПРОЦЕСС АМЖИЛТТАЙ ДУУСЛАА ---'))
        self.stdout.write(f'Төгссөн: {graduated}, анги ахисан: {sum(advanced.values())}. Лог: {log_path()}')
