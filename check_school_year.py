#!/usr/bin/env python
"""SchoolYear model шалгах скрипт"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mmo.settings')
django.setup()

from olympiad.models import SchoolYear, Olympiad

print("\n=== SchoolYear Model ===\n")

# Бүх school year-үүд
all_school_years = SchoolYear.objects.all().order_by('-id')

print(f"Нийт school year: {all_school_years.count()}\n")

# is_current талбар байгаа эсэхийг шалгах
first_sy = all_school_years.first()
if first_sy:
    print(f"SchoolYear талбарууд: {[f.name for f in first_sy._meta.fields]}\n")

# Current school year олох
current_sy = None
if hasattr(SchoolYear, 'is_current'):
    current_sy = SchoolYear.objects.filter(is_current=True).first()
    print(f"Current school year (is_current=True): {current_sy.name if current_sy else 'None'}\n")
else:
    print("SchoolYear model-д 'is_current' талбар байхгүй байна.\n")

# Бүх school year-үүд
print("Бүх school years:")
for sy in all_school_years[:10]:
    olympiad_count = Olympiad.objects.filter(school_year=sy).count()
    is_current = getattr(sy, 'is_current', None)
    print(f"  - {sy.name} (ID={sy.id}) - {olympiad_count} олимпиад", end='')
    if is_current is not None:
        print(f" - is_current={is_current}")
    else:
        print()

# Round 2 олимпиадуудын school year-үүд
print("\nRound 2 олимпиадуудын school year статистик:")
round2_olympiads = Olympiad.objects.filter(round=2).select_related('school_year')
sy_counts = {}
for oly in round2_olympiads:
    sy_name = oly.school_year.name if oly.school_year else 'None'
    sy_counts[sy_name] = sy_counts.get(sy_name, 0) + 1

for sy_name, count in sorted(sy_counts.items()):
    print(f"  - {sy_name}: {count} олимпиад")
