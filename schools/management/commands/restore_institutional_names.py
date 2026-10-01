"""
Сургуулийн удирдлага (s0001) болон аймаг/дүүргийн удирдах ажилтны (padmin01) албан аккаунтуудын
нэрийг сургууль/аймгийн нэрээр сэргээнэ. Хувь хүний нэр оруулсан, эсвэл сургуулийн нэр/аймаг
өөрчлөгдсөний дараа хуучирсан нэрийг засна.

    python manage.py restore_institutional_names            # юу өөрчлөгдөхийг харуулна
    python manage.py restore_institutional_names --apply    # хадгална (хуучин утгыг logs/-д CSV болгоно)
"""
import csv
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Province
from schools.institutional import (apply_names, is_province_contact_account, is_school_manager_account,
                                   province_contact_names, school_manager_names)
from schools.models import School


class Command(BaseCommand):
    help = 'Сургууль, аймгийн албан аккаунтуудын нэрийг сургууль/аймгийн нэрээр сэргээнэ.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Өөрчлөлтийг хадгална')

    def handle(self, *args, **opts):
        moderator_ids = set(School.objects.exclude(user=None).values_list('user_id', flat=True))
        changes = []  # (user, хуучин first, хуучин last, шалтгаан)

        for school in School.objects.select_related('manager', 'province').exclude(manager=None):
            user = school.manager
            if not is_school_manager_account(user) or user.id in moderator_ids:
                continue  # хувь хүний аккаунт менежерээр томилогдсон
            old = (user.first_name, user.last_name)
            if apply_names(user, school_manager_names(school, role=user.first_name)):
                changes.append((user, *old, f'сургууль #{school.id}'))

        for province in Province.objects.select_related('contact_person').exclude(contact_person=None):
            user = province.contact_person
            if not is_province_contact_account(user):
                continue
            old = (user.first_name, user.last_name)
            if apply_names(user, province_contact_names(province)):
                changes.append((user, *old, f'аймаг #{province.id}'))

        for user, old_first, old_last, where in changes:
            self.stdout.write(f'  {user.username:9} {where:14} "{old_last} {old_first}" → "{user.last_name} {user.first_name}"')
        self.stdout.write(f'Нийт {len(changes)} аккаунт.')

        if not opts['apply']:
            self.stdout.write(self.style.WARNING('Хадгалаагүй. --apply-тай ажиллуулна уу.'))
            return
        if not changes:
            return

        log_dir = os.path.join(settings.BASE_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, f'restore_institutional_names_{timezone.localtime():%Y%m%d_%H%M%S}.csv')
        with transaction.atomic(), open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['user_id', 'username', 'where', 'old_first_name', 'old_last_name', 'new_first_name', 'new_last_name'])
            for user, old_first, old_last, where in changes:
                user.save(update_fields=['first_name', 'last_name'])
                writer.writerow([user.id, user.username, where, old_first, old_last, user.first_name, user.last_name])
        self.stdout.write(self.style.SUCCESS(f'Хадгаллаа. Хуучин утга: {path}'))
