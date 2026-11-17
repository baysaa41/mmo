"""
Системийн түр бүртгэлүүдийг UserMeta.is_placeholder-ээр тэмдэглэнэ (mmo-system-accounts, 7 хоног 1).

  python manage.py mark_placeholders           # dry-run: бүлэг бүрийн тоо
  python manage.py mark_placeholders --apply   # тэмдэглэнэ (дахин ажиллуулахад аюулгүй)

Зөвхөн тэмдэглэнэ — хэрэглэгч, дүнг өөрчлөхгүй, устгахгүй.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import UserMeta
from accounts.placeholders import placeholder_groups


class Command(BaseCommand):
    help = 'Системийн түр (placeholder) бүртгэлийг UserMeta.is_placeholder-ээр тэмдэглэнэ'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Тэмдэглэх (өгөхгүй бол зөвхөн тоолно)')

    def handle(self, *args, **options):
        apply = options['apply']
        total = 0
        with transaction.atomic():
            for source, users in placeholder_groups():
                n_users = users.count()
                no_meta = users.filter(data__isnull=True).count()
                metas = UserMeta.objects.filter(user__in=users)
                already = metas.filter(is_placeholder=True).count()
                logged_in = users.filter(last_login__isnull=False).count()
                self.stdout.write(
                    f'{source:<10} хэрэглэгч {n_users:>6} · UserMeta-гүй {no_meta:>3} · '
                    f'өмнө тэмдэглэсэн {already:>6} · нэвтэрч байсан {logged_in:>3}')
                if apply:
                    # Өөр эх-ээр тэмдэглэгдсэнийг (жишээ нь давхар таарсан) дарж бичихгүй
                    metas.filter(is_placeholder=False).update(is_placeholder=True, placeholder_source=source)
                total += n_users - no_meta
        marked = UserMeta.objects.filter(is_placeholder=True).count()
        if apply:
            self.stdout.write(self.style.SUCCESS(f'\nТэмдэглэгдсэн нийт placeholder: {marked}'))
        else:
            self.stdout.write(self.style.WARNING(f'\nDry-run: {total} UserMeta тэмдэглэгдэнэ (--apply). Одоо: {marked}'))
        unflagged_sys = User.objects.filter(email__in=['auto-user@mmo.mn']).filter(data__is_placeholder=False).count()
        if apply and unflagged_sys:
            self.stdout.write(self.style.WARNING(f'Анхаар: тэмдэглэгдээгүй auto-user үлдлээ: {unflagged_sys}'))
