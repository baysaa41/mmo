#!/usr/bin/env python
"""Award мэдээлэл шалгах"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mmo.settings')
django.setup()

from olympiad.models import Olympiad, Award, ScoreSheet

print("\n=== Award мэдээлэл ===\n")

# Нийт Award
total_awards = Award.objects.count()
print(f"Нийт Award: {total_awards}\n")

# Award төрлүүд
print("Award төрлүүд:")
place_counts = {}
for award in Award.objects.all():
    place = award.place
    if place not in place_counts:
        place_counts[place] = 0
    place_counts[place] += 1

for place, count in sorted(place_counts.items(), key=lambda x: -x[1])[:20]:
    print(f"  {place}: {count} сурагч")

print()

# 2.1 эрхтэй сурагчид
r21_awards = Award.objects.filter(place__startswith='2.1')
print(f"\n2.1 эрхтэй сурагч: {r21_awards.count()}")

if r21_awards.exists():
    print("\nЖишээ:")
    for award in r21_awards[:5]:
        print(f"  - {award.contestant.last_name} {award.contestant.first_name}")
        print(f"    Place: {award.place}")
        print(f"    Olympiad: {award.olympiad.name} (ID={award.olympiad.id})")
        print()

# Round 2 олимпиадууд бүлэгтэй
round2_with_group = Olympiad.objects.filter(round=2, group__isnull=False)
print(f"\nRound 2 олимпиад (бүлэгтэй): {round2_with_group.count()}")

for r2 in round2_with_group:
    print(f"\n  {r2.name} (ID={r2.id})")
    print(f"    Бүлэг: {r2.group.name}")
    print(f"    Бүлгийн гишүүд: {r2.group.user_set.count()}")

    # Round 1 олимпиад
    r1s = Olympiad.objects.filter(next_round=r2)
    print(f"    Round 1 олимпиад (next_round={r2.id}): {r1s.count()}")
