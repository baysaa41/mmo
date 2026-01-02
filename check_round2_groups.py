#!/usr/bin/env python
"""Round2 бүлгүүдийг шалгах скрипт"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mmo.settings')
django.setup()

from django.contrib.auth.models import Group
from olympiad.models import Olympiad

# Round2 бүлгүүдийг олох
round2_groups = Group.objects.filter(name__startswith='Round2_')

print(f'\n=== Round2 бүлгүүд ===')
print(f'Нийт: {round2_groups.count()} бүлэг\n')

for group in round2_groups:
    user_count = group.user_set.count()
    # Энэ бүлэгтэй холбоотой олимпиадууд
    olympiads = Olympiad.objects.filter(group=group)
    olympiad_names = ', '.join([o.name for o in olympiads]) if olympiads.exists() else 'Олимпиадгүй'

    print(f'• {group.name}')
    print(f'  - Хэрэглэгч: {user_count}')
    print(f'  - Олимпиад: {olympiad_names}')
    print()
