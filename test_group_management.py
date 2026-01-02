#!/usr/bin/env python
"""Group management helper функцүүдийг тестлэх скрипт"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mmo.settings')
django.setup()

from olympiad.models import Olympiad
from olympiad.utils.group_management import ensure_olympiad_has_group, get_or_create_round2_group
from django.contrib.auth.models import Group

print("\n=== Group Management Helper Functions Test ===\n")

# Round 2 олимпиадуудыг олох
round2_olympiads = Olympiad.objects.filter(round=2)[:5]

print(f"Тестлэх олимпиад: {round2_olympiads.count()}\n")

for olympiad in round2_olympiads:
    print(f"Олимпиад: {olympiad.name} (ID={olympiad.id})")
    print(f"  Одоогийн бүлэг: {olympiad.group.name if olympiad.group else 'None'}")

    # ensure_olympiad_has_group тестлэх
    group, created = ensure_olympiad_has_group(olympiad)

    if created:
        print(f"  ✓ Шинэ бүлэг үүссэн: {group.name}")
    else:
        print(f"  ↻ Бүлэг аль хэдийн байсан: {group.name}")

    # Олимпиадын group талбар шинэчлэгдсэн эсэхийг шалгах
    olympiad.refresh_from_db()
    print(f"  Одоогийн бүлэг: {olympiad.group.name if olympiad.group else 'None'}")
    print(f"  Бүлгийн гишүүд: {group.user_set.count()}\n")

print("\n=== Тест дууслаа ===")

# Статистик
total_round2 = Olympiad.objects.filter(round=2).count()
with_group = Olympiad.objects.filter(round=2, group__isnull=False).count()
without_group = Olympiad.objects.filter(round=2, group__isnull=True).count()

print(f"\nНийт Round 2 олимпиад: {total_round2}")
print(f"Бүлэгтэй: {with_group}")
print(f"Бүлэггүй: {without_group}")
