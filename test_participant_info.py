#!/usr/bin/env python
"""Оролцогчдын Round 1 мэдээлэл тестлэх"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mmo.settings')
django.setup()

from olympiad.models import Olympiad, Award, ScoreSheet
from accounts.models import Province
from django.contrib.auth.models import User

print("\n=== Оролцогчдын Round 1 мэдээлэл тест ===\n")

# Round 2 олимпиад сонгох
round2_olympiad = Olympiad.objects.filter(round=2).first()

if not round2_olympiad:
    print("Round 2 олимпиад олдсонгүй!")
    exit()

print(f"Тестлэх олимпиад: {round2_olympiad.name} (ID={round2_olympiad.id})")
print(f"Бүлэг: {round2_olympiad.group.name if round2_olympiad.group else 'None'}\n")

# Round 1 олимпиадууд
round1_olympiads = Olympiad.objects.filter(next_round=round2_olympiad)
print(f"Round 1 олимпиадууд: {round1_olympiads.count()}")
for r1 in round1_olympiads:
    print(f"  - {r1.name} (ID={r1.id})")

print()

# Эхний аймаг сонгох
province = Province.objects.first()
if not province:
    print("Аймаг олдсонгүй!")
    exit()

print(f"\nТестлэх аймаг: {province.name}\n")

# Энэ аймгийн оролцогчид
if round2_olympiad.group:
    participants = round2_olympiad.group.user_set.filter(
        data__province=province
    )[:5]  # Эхний 5

    print(f"Оролцогч: {participants.count()} (эхний 5)\n")

    for user in participants:
        print(f"• {user.last_name} {user.first_name} (ID={user.id})")

        # Award олох
        award = Award.objects.filter(
            olympiad__in=round1_olympiads,
            contestant=user
        ).first()

        if award:
            print(f"  Award: {award.place} (Olympiad ID={award.olympiad.id})")
        else:
            print(f"  Award: Олдсонгүй")

        # ScoreSheet олох
        scoresheet = ScoreSheet.objects.filter(
            olympiad__in=round1_olympiads,
            user=user,
            is_official=True
        ).order_by('-total').first()

        if scoresheet:
            print(f"  ScoreSheet: {scoresheet.total} оноо (Olympiad ID={scoresheet.olympiad.id})")
        else:
            print(f"  ScoreSheet: Олдсонгүй")

        print()
else:
    print("Олимпиадад бүлэг байхгүй байна!")

# Бүх Award-ийн төрлүүд
print("\n=== Award төрлүүд ===\n")
award_types = Award.objects.filter(
    olympiad__in=round1_olympiads
).values_list('place', flat=True).distinct()

for place in award_types:
    count = Award.objects.filter(
        olympiad__in=round1_olympiads,
        place=place
    ).count()
    print(f"  {place}: {count} сурагч")

print()
