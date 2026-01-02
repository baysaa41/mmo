#!/usr/bin/env python
"""Олимпиад 202-ын мэдээлэл тестлэх"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mmo.settings')
django.setup()

from olympiad.models import Olympiad, Award, ScoreSheet
from accounts.models import Province

print("\n=== Олимпиад 202 тест ===\n")

# Round 2 олимпиад
olympiad = Olympiad.objects.get(id=202)
print(f"Round 2: {olympiad.name} (ID={olympiad.id})")
print(f"Бүлэг: {olympiad.group.name}")
print(f"Бүлгийн гишүүд: {olympiad.group.user_set.count()}\n")

# Round 1 олимпиад
round1_olympiads = Olympiad.objects.filter(next_round=olympiad)
print(f"Round 1 олимпиадууд: {round1_olympiads.count()}")
for r1 in round1_olympiads:
    print(f"  - {r1.name} (ID={r1.id})\n")

# Аймаг сонгох
province = Province.objects.first()
print(f"Тестлэх аймаг: {province.name}\n")

# Энэ аймгийн оролцогчид
participants = olympiad.group.user_set.filter(
    data__province=province
).select_related('data__school', 'data__grade')[:5]

print(f"Оролцогч ({province.name}): {participants.count()} (эхний 5)\n")

for user in participants:
    print(f"• {user.last_name} {user.first_name} (ID={user.id})")

    school_name = user.data.school.name if hasattr(user, 'data') and user.data.school else 'Сургуулиа бүртгээгүй'
    grade_name = user.data.grade.name if hasattr(user, 'data') and user.data.grade else '-'

    print(f"  Сургууль: {school_name}")
    print(f"  Анги: {grade_name}")

    # Award олох
    award = Award.objects.filter(
        olympiad__in=round1_olympiads,
        contestant=user
    ).first()

    if award:
        print(f"  ✓ Award: {award.place}")
    else:
        print(f"  ✗ Award: Олдсонгүй")

    # ScoreSheet олох
    scoresheet = ScoreSheet.objects.filter(
        olympiad__in=round1_olympiads,
        user=user,
        is_official=True
    ).order_by('-total').first()

    if scoresheet:
        print(f"  ✓ ScoreSheet: {scoresheet.total} оноо")
    else:
        print(f"  ✗ ScoreSheet: Олдсонгүй")

    print()

# Статистик
print("\n=== Статистик ===\n")

# Нийт оролцогч
all_participants = olympiad.group.user_set.all()
print(f"Нийт оролцогч: {all_participants.count()}")

# Award-тай оролцогч
with_award = 0
without_award = 0

for user in all_participants[:100]:  # Эхний 100 шалгах
    award = Award.objects.filter(
        olympiad__in=round1_olympiads,
        contestant=user
    ).exists()

    if award:
        with_award += 1
    else:
        without_award += 1

print(f"\nЭхний 100 оролцогч:")
print(f"  Award-тай: {with_award}")
print(f"  Award-гүй: {without_award}")
