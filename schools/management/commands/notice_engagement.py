"""
send_registration_notice-ийн илгээлтийн үр дүн: хүргэгдсэн, нээсэн, холбоос дарсан, системд нэвтэрсэн.

    python manage.py notice_engagement                      # logs/registration_notice_*.csv бүгд
    python manage.py notice_engagement --log logs/registration_notice_20261001_014843.csv --xlsx

Нээлтийг SES-ийн tracking pixel-ээр бүртгэдэг тул зураг хаадаг имэйл программ дээр
бүртгэгдэхгүй, Apple Mail урьдчилан ачаалснаар илүү тоологдож болно — ойролцоо тоо.
"""
import csv
import glob
import os
from collections import defaultdict
from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from emails.models import EmailEvent
from schools.models import School


class Command(BaseCommand):
    help = 'Бүртгэлийн имэйлийн хүргэлт, нээлт, холбоос дарсан, нэвтэрсэн байдлын тайлан.'

    def add_arguments(self, parser):
        parser.add_argument('--log', nargs='+', help='Илгээлтийн лог(ууд) (анхдагч: logs/registration_notice_*.csv)')
        parser.add_argument('--xlsx', action='store_true', help='Хүлээн авагч бүрийн дэлгэрэнгүйг Excel-д гаргана')

    def handle(self, *args, **opts):
        paths = opts['log'] or sorted(glob.glob(os.path.join(settings.BASE_DIR, 'logs', 'registration_notice_*.csv')))
        sends = {}  # email -> хамгийн сүүлийн бодит илгээлт
        for path in paths:
            with open(path, newline='', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    if row['status'] == 'sent' and row['message_id']:
                        row['sent_at'] = datetime.fromisoformat(row['time'])
                        if row['email'] not in sends or sends[row['email']]['sent_at'] < row['sent_at']:
                            sends[row['email']] = row
        if not sends:
            self.stdout.write('Илгээлтийн бүртгэл олдсонгүй.')
            return

        events = defaultdict(dict)  # message_id -> {event_type: эхний огноо}
        for message_id, event_type, occurred_at in EmailEvent.objects.filter(
                message_id__in=[r['message_id'] for r in sends.values()]
        ).values_list('message_id', 'event_type', 'occurred_at').order_by('occurred_at'):
            events[message_id].setdefault(event_type, occurred_at)

        user_ids = {int(uid) for r in sends.values() for uid in r['user_ids'].split()}
        users = User.objects.select_related('data').in_bulk(user_ids)
        province_of = {}
        for school in School.objects.select_related('province').filter(user_id__in=user_ids):
            province_of.setdefault(school.user_id, school.province.name)
        for school in School.objects.select_related('province').filter(manager_id__in=user_ids):
            province_of.setdefault(school.manager_id, school.province.name)

        rows = []
        for email, send in sends.items():
            uids = [int(u) for u in send['user_ids'].split()]
            ev = events.get(send['message_id'], {})
            logged_in = None
            for uid in uids:
                u = users.get(uid)
                if not u:
                    continue
                la = getattr(getattr(u, 'data', None), 'last_activity', None)
                latest = max(filter(None, [la, u.last_login]), default=None)
                if latest and latest >= send['sent_at'] and (logged_in is None or latest > logged_in):
                    logged_in = latest
            rows.append({
                'email': email, 'roles': send['roles'],
                'province': next((province_of[u] for u in uids if u in province_of), '—'),
                'sent_at': send['sent_at'], 'delivered': ev.get('delivery'), 'opened': ev.get('open'),
                'clicked': ev.get('click'), 'logged_in': logged_in,
            })

        self._print(rows)
        if opts['xlsx']:
            self._xlsx(rows)

    def _print(self, rows):
        def pct(n, d):
            return f'{n:4} ({round(100 * n / d) if d else 0:3}%)'

        total = len(rows)
        count = lambda key, rs=rows: sum(1 for r in rs if r[key])
        first_send = min(r['sent_at'] for r in rows)
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Илгээсэн: {total} хаяг (эхний илгээлт {timezone.localtime(first_send):%Y-%m-%d %H:%M}, '
            f'одоо {timezone.localtime():%Y-%m-%d %H:%M})'))
        for label, key in [('Хүргэгдсэн', 'delivered'), ('Нээсэн', 'opened'),
                           ('Холбоос дарсан', 'clicked'), ('Системд нэвтэрсэн', 'logged_in')]:
            self.stdout.write(f'  {label:18} {pct(count(key), total)}')

        by_province = defaultdict(list)
        for r in rows:
            by_province[r['province']].append(r)
        self.stdout.write('\n  {:36} {:>5} {:>11} {:>11} {:>11}'.format('Аймаг/дүүрэг', 'Илг.', 'Нээсэн', 'Дарсан', 'Нэвтэрсэн'))
        for province, rs in sorted(by_province.items(), key=lambda x: count('opened', x[1]) / len(x[1])):
            self.stdout.write('  {:36} {:5} {:>11} {:>11} {:>11}'.format(
                province, len(rs), pct(count('opened', rs), len(rs)),
                pct(count('clicked', rs), len(rs)), pct(count('logged_in', rs), len(rs))))

    def _xlsx(self, rows):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = 'Хүлээн авагчид'
        fmt = lambda d: timezone.localtime(d).strftime('%Y-%m-%d %H:%M') if d else ''
        ws.append(['Имэйл', 'Үүрэг', 'Аймаг/дүүрэг', 'Илгээсэн', 'Хүргэгдсэн', 'Нээсэн', 'Холбоос дарсан', 'Нэвтэрсэн'])
        for r in sorted(rows, key=lambda r: (r['province'], r['email'])):
            ws.append([r['email'], r['roles'], r['province'], fmt(r['sent_at']), fmt(r['delivered']),
                       fmt(r['opened']), fmt(r['clicked']), fmt(r['logged_in'])])
        ws.freeze_panes = 'A2'
        ws.auto_filter.ref = ws.dimensions
        path = os.path.join(settings.BASE_DIR, 'logs', f'notice_engagement_{timezone.localtime():%Y%m%d_%H%M%S}.xlsx')
        wb.save(path)
        self.stdout.write(f'\nExcel: {path}')
