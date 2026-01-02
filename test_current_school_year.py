#!/usr/bin/env python
"""Одоогийн хичээлийн жил тестлэх"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mmo.settings')
django.setup()

from olympiad.models import SchoolYear, Olympiad
from django.utils import timezone

print("\n=== Одоогийн хичээлийн жил тест ===\n")

# Одоогийн огноо
today = timezone.now().date()
print(f"Өнөөдрийн огноо: {today}\n")

# Одоогийн хичээлийн жилийг олох
current_school_year = SchoolYear.get_current()

if current_school_year:
    print(f"Одоогийн хичээлийн жил: {current_school_year.name}")
    print(f"  Эхлэх: {current_school_year.start}")
    print(f"  Дуусах: {current_school_year.end}")
    is_active = current_school_year.is_current if hasattr(current_school_year, 'is_current') else 'N/A'
    print(f"  Идэвхтэй эсэх: {is_active}\n")

    # Энэ хичээлийн жилийн Round 2 олимпиадууд
    round2_olympiads = Olympiad.objects.filter(
        round=2,
        school_year=current_school_year
    ).select_related('level', 'school_year', 'group', 'host')

    print(f"Round 2 олимпиад ({current_school_year.name}): {round2_olympiads.count()}\n")

    for olympiad in round2_olympiads:
        print(f"  • {olympiad.name}")
        print(f"    - Түвшин: {olympiad.level.name if olympiad.level else 'None'}")
        print(f"    - Бүлэг: {olympiad.group.name if olympiad.group else 'None'}")
        print(f"    - Host: {olympiad.host.name if olympiad.host else 'None'}")
        print()
else:
    print("⚠️ Одоогийн хичээлийн жил олдсонгүй!\n")

    # Бүх хичээлийн жилүүд
    print("Бүх хичээлийн жилүүд:")
    for sy in SchoolYear.objects.all().order_by('-start')[:5]:
        print(f"  - {sy.name}: {sy.start} → {sy.end}")

    # Хамгийн сүүлийн хичээлийн жил
    latest = SchoolYear.get_latest()
    if latest:
        print(f"\nХамгийн сүүлийн: {latest.name}")

print("\n=== Бүх Round 2 олимпиадуудын статистик ===\n")

all_round2 = Olympiad.objects.filter(round=2).select_related('school_year')
sy_stats = {}

for olympiad in all_round2:
    sy_name = olympiad.school_year.name if olympiad.school_year else 'None'
    if sy_name not in sy_stats:
        sy_stats[sy_name] = 0
    sy_stats[sy_name] += 1

for sy_name in sorted(sy_stats.keys(), reverse=True):
    count = sy_stats[sy_name]
    print(f"  {sy_name}: {count} олимпиад")

print(f"\nНийт: {all_round2.count()} олимпиад")
