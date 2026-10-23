"""
Энэ хичээлийн жил mmo.mn-д шинээр бүртгүүлсэн сургуулиудыг аймаг/дүүргийн мэргэжилтнүүдээр (Province-ийн
админууд) баталгаажуулуулах лавлагаа илгээнэ. Сургуулийн бүртгэлийн хүсэлтийг шалгуургүй хүлээн авдаг тул.

School-д үүсгэсэн огноо байхгүй тул удирдлагын s-аккаунт (School.manager) үүссэн огноогоор шинэ эсэхийг тогтооно.
Хаяг бүрт зөвхөн өмнө нь лавлаагүй (logs/new_school_check_*.csv-д «sent» болоогүй) сургуулиудыг илгээнэ —
шинээр сургууль бүртгэх бүрт дахин ажиллуулахад тухайн сургуулийн лавлагаа л явна.

  python manage.py send_new_school_check                                 # тоо, жишээ (юу ч илгээхгүй)
  python manage.py send_new_school_check --test-email me@example.com --province 22
  python manage.py send_new_school_check --send
"""
import csv
import glob
import os
import time
from collections import defaultdict
from datetime import date, datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone

from emails.html import text_to_html
from schools.models import School
from schools.moderator import NOTICE_FROM_EMAIL as FROM_EMAIL, blocked_emails, norm_email, province_admins

LOG_GLOB = 'new_school_check_*.csv'
SINCE = date(2026, 8, 1)  # энэ хичээлийн жил
TEMPLATE = 'schools/emails/province/new_school_check.txt'


class Command(BaseCommand):
    help = 'Шинээр бүртгүүлсэн сургуулиудыг аймаг/дүүргийн мэргэжилтнүүдээр баталгаажуулуулах лавлагаа илгээнэ.'

    def add_arguments(self, parser):
        parser.add_argument('--province', type=int, nargs='+', help='Зөвхөн эдгээр аймаг/дүүрэг (ID)')
        parser.add_argument('--test-email', help='Имэйлүүдийг зөвхөн энэ хаяг руу илгээнэ')
        parser.add_argument('--send', action='store_true', help='Бодитоор илгээнэ')
        parser.add_argument('--yes', action='store_true', help='--send үед баталгаажуулалт асуухгүй')
        parser.add_argument('--rate', type=float, default=5, help='Секундэд илгээх дээд тоо')

    def handle(self, *args, **opts):
        self.blocked = blocked_emails()
        by_province = self._schools(opts['province'])
        messages, no_admin = self._messages(by_province)
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Аймаг/дүүрэг: {len(by_province)}, сургууль: {sum(len(v) for v in by_province.values())} | '
            f'имэйл: {len(messages)} | илгээгч: {FROM_EMAIL}'))
        for name in no_admin:
            self.stdout.write(self.style.WARNING(f'  Админгүй / имэйл хүрэхгүй: {name}'))
        if opts['test_email']:
            for m in messages:
                self._email(m, opts['test_email'], f'[ТЕСТ → {m["email"]}] {m["subject"]}').send()
                self.stdout.write(self.style.SUCCESS(f'Тест: {m["province"]} → {opts["test_email"]}'))
        elif opts['send']:
            self._send_all(messages, opts)
        else:
            for m in messages[:1]:
                self.stdout.write('=' * 72 + f'\nTo: {m["email"]}\nSubject: {m["subject"]}\n' + '-' * 72 + f'\n{m["body"]}')
            for m in messages:
                self.stdout.write(f'  {m["count"]:3}  {m["province"][:30]:30} {m["email"]}')
            self.stdout.write(self.style.WARNING('Юу ч илгээгээгүй. --test-email эсвэл --send ашиглана уу.'))

    def _schools(self, province_ids):
        qs = (School.objects.filter(manager__date_joined__date__gte=SINCE)
              .select_related('province', 'user', 'manager', 'group').order_by('province__name', 'id'))
        if province_ids:
            qs = qs.filter(province_id__in=province_ids)
        out = defaultdict(list)
        for s in qs:
            out[s.province].append({
                'id': s.id, 'name': s.name,
                'created': timezone.localtime(s.manager.date_joined).strftime('%Y-%m-%d'),
                'created_at': s.manager.date_joined,
                'registrar': s.user.get_full_name() if s.user else '',
                'registrar_email': s.user.email if s.user else '',
                'students': s.group.user_set.count() if s.group else 0,
            })
        return out

    def _messages(self, by_province):
        sent = self._already_sent(by_province)
        messages, no_admin = [], []
        for province, all_schools in by_province.items():
            admins = province_admins(province, self.blocked)
            if not admins:
                no_admin.append(province.name)
                continue
            for email in sorted({norm_email(u.email) for u in admins}):
                schools = [s for s in all_schools if (email, s['id']) not in sent]
                if not schools:
                    continue
                body = render_to_string(TEMPLATE, {'province': province.name, 'count': len(schools),
                                                   'schools': schools, 'from_email': FROM_EMAIL})
                messages.append({'email': email, 'province_id': province.id, 'province': province.name,
                                 'count': len(schools), 'school_ids': ' '.join(str(s['id']) for s in schools),
                                 'subject': f'Лавлагаа: {province.name} — mmo.mn-д шинээр бүртгүүлсэн {len(schools)} сургууль',
                                 'body': body, 'html': text_to_html(body)})
        return messages, no_admin

    def _email(self, m, to, subject=None):
        msg = EmailMultiAlternatives(subject=subject or m['subject'], body=m['body'], from_email=FROM_EMAIL,
                                     to=[to], reply_to=[FROM_EMAIL])
        msg.attach_alternative(m['html'], 'text/html')
        return msg

    def _log_dir(self):
        return os.path.join(settings.BASE_DIR, 'logs')

    def _already_sent(self, by_province):
        """{(email, school_id)} — аль хэдийн лавласан. Эхний логт school_ids багана байхгүй тул тухайн
        аймгийн илгээх үеэс өмнө бүртгэгдсэн сургуулиудыг лавласан гэж үзнэ."""
        by_pid = {p.id: schools for p, schools in by_province.items()}
        sent = set()
        for path in glob.glob(os.path.join(self._log_dir(), LOG_GLOB)):
            with open(path, newline='', encoding='utf-8-sig') as f:
                for r in csv.DictReader(f):
                    if r['status'] != 'sent':
                        continue
                    if r.get('school_ids'):
                        ids = [int(x) for x in r['school_ids'].split()]
                    else:
                        at = datetime.fromisoformat(r['time'])
                        ids = [s['id'] for s in by_pid.get(int(r['province_id']), []) if s['created_at'] <= at]
                    sent |= {(r['email'], i) for i in ids}
        return sent

    def _send_all(self, messages, opts):
        if not messages:
            self.stdout.write('Илгээх имэйл алга.')
            return
        if not opts['yes'] and input(f'{len(messages)} имэйл илгээх үү? [yes/no]: ').strip().lower() != 'yes':
            self.stdout.write('Цуцаллаа.')
            return
        os.makedirs(self._log_dir(), exist_ok=True)
        log_path = os.path.join(self._log_dir(), f'new_school_check_{timezone.localtime():%Y%m%d_%H%M%S}.csv')
        connection = get_connection()
        sent = failed = 0
        with open(log_path, 'w', newline='', encoding='utf-8') as f:
            log = csv.writer(f)
            log.writerow(['province_id', 'email', 'count', 'school_ids', 'status', 'message_id', 'error', 'time'])
            for m in messages:
                msg = self._email(m, m['email'])
                msg.connection = connection
                try:
                    msg.send()
                    status = getattr(msg, 'anymail_status', None)
                    log.writerow([m['province_id'], m['email'], m['count'], m['school_ids'], 'sent',
                                  getattr(status, 'message_id', '') or '', '', timezone.now().isoformat()])
                    sent += 1
                except Exception as exc:
                    log.writerow([m['province_id'], m['email'], m['count'], m['school_ids'], 'failed', '', str(exc)[:300],
                                  timezone.now().isoformat()])
                    failed += 1
                f.flush()
                time.sleep(1 / opts['rate'] if opts['rate'] > 0 else 0)
        self.stdout.write(self.style.SUCCESS(f'Илгээсэн: {sent}, алдаа: {failed}. Лог: {log_path}'))
