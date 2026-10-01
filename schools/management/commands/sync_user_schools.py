"""
UserMeta.school / province-ийг сургуулийн группт (батлагдсан гишүүнчлэл) тааруулна — зөвхөн аюулгүй тохиолдолд:
  - профайлд сургууль хоосон, ганц сургуулийн группт байгаа → тэр сургуулиар бөглөнө
  - сургууль таарсан ч аймаг нь өөр → сургуулийн аймгаар засна

Хүрэхгүй (logs/sync_user_schools_conflicts_*.csv-д гаргана):
  - олон сургуулийн группт байгаа хэрэглэгч (аль нь зөв болохыг мэдэхгүй)
  - профайлын сургууль группынхоос өөр (сурагч өөрөө сургуулиа сольсон байж болно)

    python manage.py sync_user_schools            # юу өөрчлөгдөхийг харуулна
    python manage.py sync_user_schools --apply    # хадгална, logs/sync_user_schools.log-д бичнэ
"""
import csv
import getpass
import json
import os
from collections import defaultdict

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import UserMeta
from schools.models import School


class Command(BaseCommand):
    help = 'Хэрэглэгчийн профайлын сургууль, аймгийг сургуулийн группт аюулгүйгээр тааруулна.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Өөрчлөлтийг хадгална')

    def handle(self, *args, **opts):
        schools = {s.group_id: s for s in School.objects.exclude(group=None).select_related('province')}
        membership = defaultdict(list)
        for user_id, group_id in User.groups.through.objects.filter(
                group_id__in=schools).values_list('user_id', 'group_id'):
            membership[user_id].append(schools[group_id])

        metas = {m.user_id: m for m in UserMeta.objects.filter(user_id__in=membership)
                 .only('user_id', 'school_id', 'province_id')}

        fill_school, fix_province, conflicts = [], [], []
        for user_id, user_schools in membership.items():
            meta = metas.get(user_id)
            if meta is None:
                continue
            if len(user_schools) > 1:
                conflicts.append((user_id, 'олон сургуулийн группт', meta.school_id,
                                  ' '.join(str(s.id) for s in user_schools)))
                continue
            school = user_schools[0]
            if meta.school_id is None:
                fill_school.append((meta, school))
            elif meta.school_id != school.id:
                conflicts.append((user_id, 'профайлын сургууль группынхоос өөр', meta.school_id, str(school.id)))
            elif meta.province_id != school.province_id:
                fix_province.append((meta, school))

        self.stdout.write(f'Сургуулийн группийн гишүүн: {len(membership)}')
        self.stdout.write(f'  Сургууль хоосон → бөглөнө: {len(fill_school)}')
        self.stdout.write(f'  Аймаг зөрсөн → засна: {len(fix_province)}')
        self.stdout.write(f'  Зөрчилтэй → хүрэхгүй: {len(conflicts)}')

        log_dir = os.path.join(settings.BASE_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        stamp = f'{timezone.localtime():%Y%m%d_%H%M%S}'
        if conflicts:
            path = os.path.join(log_dir, f'sync_user_schools_conflicts_{stamp}.csv')
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['user_id', 'шалтгаан', 'профайлын сургууль', 'группийн сургууль(ууд)'])
                writer.writerows(conflicts)
            self.stdout.write(f'  Зөрчлийн жагсаалт: {path}')

        if not opts['apply']:
            self.stdout.write(self.style.WARNING('Хадгалаагүй. --apply-тай ажиллуулна уу.'))
            return

        with transaction.atomic():
            # queryset.update нь UserMeta.save()-ийн "хуучин группээс хасах" hook-ийг ажиллуулахгүй —
            # энд группийн гишүүнчлэл өөрчлөгдөхгүй тул хүссэн үйлдэл.
            for meta, school in fill_school:
                UserMeta.objects.filter(pk=meta.pk).update(school=school, province=school.province)
            for meta, school in fix_province:
                UserMeta.objects.filter(pk=meta.pk).update(province=school.province)

        with open(os.path.join(log_dir, 'sync_user_schools.log'), 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'time': timezone.localtime().isoformat(timespec='seconds'), 'user': getpass.getuser(),
                'filled_school': [m.user_id for m, _ in fill_school],
                'fixed_province': [[m.user_id, m.province_id, s.province_id] for m, s in fix_province],
                'conflicts_skipped': len(conflicts),
            }, ensure_ascii=False) + '\n')
        self.stdout.write(self.style.SUCCESS(
            f'Хадгаллаа: {len(fill_school)} сургууль бөглөсөн, {len(fix_province)} аймаг зассан. '
            f'Лог: {os.path.join(log_dir, "sync_user_schools.log")}'))
