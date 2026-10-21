"""
ММО-63 I давааны өмнө аймаг/дүүргийн мэргэжилтнүүдэд (Province-ийн админууд) илгээх шинэчилсэн мэдээлэл:
харьяа сургуулиудын бүртгэлийн өнөөдрийн байдал, анхаарал шаардлагатай сургуулиуд (Excel хавсралттай),
зар түгээх хүсэлт, болзошгүй хүндрэлийн үед олимпиадын сэдвийг тэдний имэйлээр түгээх тухай.

Нэг хаяг руу нэг л имэйл; өмнөх logs/province_update_*.csv-д «sent» болсон хаягт дахин илгээхгүй.
--update-post нь пост 500-ийн «анхаарах сургуулиуд» хэсгийг шинэчилнэ (хуучныг backup хийнэ).

  python manage.py send_province_update                       # тоо, жишээ (юу ч илгээхгүй)
  python manage.py send_province_update --test-email me@example.com --province 1 28
  python manage.py send_province_update --update-post
  python manage.py send_province_update --send --exclude-province 22
"""
import csv
import glob
import io
import os
import re
import time
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import escape

from accounts.models import Province
from emails.html import text_to_html
from olympiad.models import Olympiad, SchoolYear
from schools import enrollment
from schools.models import EnrollmentLog, School
from schools.moderator import NOTICE_FROM_EMAIL as FROM_EMAIL, blocked_emails, email_problem, norm_email, province_admins

POST_ID = 500
LOG_GLOB = 'province_update_*.csv'
WEEKDAYS = ['Даваа', 'Мягмар', 'Лхагва', 'Пүрэв', 'Баасан', 'Бямба', 'Ням']
ISSUE_ACTION = {
    'Бүртгэгч багшгүй': 'Бүртгэгч багш томилох (аймаг/дүүргийн мэргэжилтэн эсвэл registration@mmo.mn)',
    'Бүртгэгч багшийн имэйл хүрэхгүй': 'Бүртгэгч багшийн имэйлийг шинэчлэх',
    'Бүртгэлтэй сурагчгүй': 'Бүртгэгч багш mmo.mn-д нэвтэрч сурагчдаа бүртгэх',
}
POST_MARK = '<h4>Анхаарал шаардлагатай сургуулиуд'


class Command(BaseCommand):
    help = 'Аймаг/дүүргийн мэргэжилтнүүдэд I давааны өмнөх шинэчилсэн мэдээлэл илгээнэ, пост 500-г шинэчилнэ.'

    def add_arguments(self, parser):
        parser.add_argument('--province', type=int, nargs='+', help='Зөвхөн эдгээр аймаг/дүүрэг (ID)')
        parser.add_argument('--exclude-province', type=int, nargs='+', default=[], help='Эдгээрийг алгасах (ID)')
        parser.add_argument('--add-recipient', nargs='+', default=[], metavar='PROVINCE_ID:EMAIL',
                            help='Province-ийн админ биш мэргэжилтнийг нэмэх (жишээ нь 22:name@moes.edu.mn)')
        parser.add_argument('--test-email', help='Сонгосон аймгуудын имэйлийг зөвхөн энэ хаяг руу илгээнэ')
        parser.add_argument('--update-post', action='store_true', help=f'Пост {POST_ID}-г шинэчилнэ')
        parser.add_argument('--send', action='store_true', help='Бодитоор илгээнэ')
        parser.add_argument('--yes', action='store_true', help='--send үед баталгаажуулалт асуухгүй')
        parser.add_argument('--rate', type=float, default=5, help='Секундэд илгээх дээд тоо')

    def handle(self, *args, **opts):
        self.today = timezone.localdate()
        self.olympiad = self._olympiad_info()
        self.blocked = blocked_emails()
        site = settings.SITE_URL.rstrip('/')
        self.base = {'olympiad': self.olympiad, 'from_email': FROM_EMAIL, 'today': f'{self.today.month}-р сарын {self.today.day}',
                     'post_url': f'{site}/post/?id={POST_ID}', 'registry_url': f'{site}/schools/registry/'}
        provinces = Province.objects.order_by('name')
        if opts['province']:
            provinces = provinces.filter(id__in=opts['province'])
        provinces = [p for p in provinces.exclude(id__in=opts['exclude_province'])]
        data = {p.id: self._province_data(p) for p in provinces}
        data = {k: v for k, v in data.items() if v['total']}

        if opts['update_post']:
            return self._update_post(data)
        self.extra = defaultdict(list)
        for item in opts['add_recipient']:
            pid, _, email = item.partition(':')
            if not pid.isdigit() or '@' not in email:
                raise CommandError(f'--add-recipient буруу: {item}')
            self.extra[int(pid)].append(norm_email(email))
        messages = self._messages(provinces, data)
        self.stdout.write(self.style.MIGRATE_HEADING(f'Хүлээн авагч: {len(messages)} хаяг, {len(data)} аймаг/дүүрэг | илгээгч: {FROM_EMAIL}'))
        for p in provinces:
            if p.id in data and not any(p.id in m['province_ids'] for m in messages):
                self.stdout.write(self.style.WARNING(f'  Имэйлтэй мэргэжилтэнгүй: {p.name} (id={p.id})'))
        if opts['test_email']:
            for m in messages:
                self._email(m, opts['test_email'], f'[ТЕСТ → {", ".join(m["to_names"])}] {m["subject"]}').send()
                self.stdout.write(self.style.SUCCESS(f'Тест: {m["subject"]} → {opts["test_email"]}'))
        elif opts['send']:
            self._send_all(messages, opts)
        else:
            for m in messages[:1]:
                self.stdout.write('=' * 72 + f'\nTo: {m["email"]}\nSubject: {m["subject"]}\n' + '-' * 72 + f'\n{m["body"]}')
            for m in messages:
                self.stdout.write(f'  {m["email"]:40} {", ".join(m["to_names"])}')
            self.stdout.write(self.style.WARNING('Юу ч илгээгээгүй. --test-email эсвэл --send ашиглана уу.'))

    # ---------------------------------------------------------------- data

    def _olympiad_info(self):
        sy = SchoolYear.objects.filter(start__lte=self.today, end__gte=self.today).first()
        olympiads = list(Olympiad.objects.filter(school_year=sy, round=1)) if sy else []
        if not olympiads:
            raise CommandError('Энэ хичээлийн жилийн I давааны олимпиад олдсонгүй.')
        start = min(timezone.localtime(o.start_time).date() for o in olympiads if o.start_time)
        eve = start - timedelta(days=1)
        return {'name': olympiads[0].name.split(',')[0],
                'date': f'{start.year} оны {start.month}-р сарын {start.day}-нд ({WEEKDAYS[start.weekday()]} гараг)',
                'eve': f'{eve.month}-р сарын {eve.day}'}

    def _this_year(self):
        """{school_id: энэ хичээлийн жилд бүртгэсэн (enroll/transfer) бөгөөд одоо ч бүлэгт байгаа сурагчийн тоо}.

        School.group нь өмнөх жилүүдийн сурагчдыг хадгалдаг тул «бүртгэлтэй сурагч» = бүх жилийнх.
        """
        if not hasattr(self, '_this_year_cache'):
            counts = defaultdict(set)
            logs = EnrollmentLog.objects.filter(
                created_at__date__gte=enrollment.current_school_year_start(),
                action__in=[EnrollmentLog.Action.ENROLL, EnrollmentLog.Action.TRANSFER], to_school__isnull=False)
            for uid, sid in logs.values_list('user_id', 'to_school_id'):
                counts[sid].add(uid)
            self._this_year_cache = counts
        return self._this_year_cache

    def _province_data(self, province):
        rows = []
        this_year = self._this_year()
        for s in (School.objects.filter(province=province).exclude(name='Бусад')
                  .select_related('user__data', 'manager', 'group').order_by('name')):
            u = s.user
            staff = [x.pk for x in (s.user, s.manager) if x]
            students = s.group.user_set.exclude(pk__in=staff).count() if s.group_id else 0
            pending = enrollment.pending_students(s).count()
            members = set(s.group.user_set.values_list('id', flat=True)) if s.group_id else set()
            new = len(this_year.get(s.id, set()) & members)
            issues = []
            if u is None or not u.is_active:
                issues.append('Бүртгэгч багшгүй')
            elif email_problem(u, self.blocked):
                issues.append('Бүртгэгч багшийн имэйл хүрэхгүй')
            if not students:
                issues.append('Бүртгэлтэй сурагчгүй')
            meta = getattr(u, 'data', None) if u else None
            rows.append({'name': s.name, 'issue': ', '.join(issues), 'issues': issues, 'students': students, 'new': new, 'pending': pending,
                         'registrar': u.get_full_name() if u else '', 'username': u.username if u else '',
                         'email': u.email if u else '', 'mobile': getattr(meta, 'mobile', '') or '',
                         'last_login': timezone.localtime(u.last_login).strftime('%Y-%m-%d') if u and u.last_login else 'хэзээ ч',
                         'manager_email': s.manager.email if s.manager else ''})
        attention = [r for r in rows if r['issues']]
        return {'province': province.name, 'total': len(rows), 'rows': rows, 'attention': attention,
                'with_students': sum(1 for r in rows if r['students']),
                'new_schools': sum(1 for r in rows if r['new']), 'new_students': sum(r['new'] for r in rows),
                'pending_students': sum(r['pending'] for r in rows), 'pending_schools': sum(1 for r in rows if r['pending'])}

    # ------------------------------------------------------------- message

    def _messages(self, provinces, data):
        by_email = defaultdict(lambda: {'province_ids': [], 'names': set()})
        for p in provinces:
            if p.id not in data:
                continue
            for u in province_admins(p, self.blocked):
                e = norm_email(u.email)
                entry = by_email[e]
                if p.id not in entry['province_ids']:
                    entry['province_ids'].append(p.id)
                entry['names'].add(u.username)
            for e in self.extra.get(p.id, []):
                entry = by_email[e]
                if p.id not in entry['province_ids']:
                    entry['province_ids'].append(p.id)
                entry['names'].add(e)
        sent = self._already_sent()
        messages = []
        for email, entry in by_email.items():
            if email in sent:
                continue
            for pid in entry['province_ids']:  # нэг хаяг олон аймаг хариуцвал аймаг тус бүрт тусдаа имэйл
                d = data[pid]
                body = render_to_string('schools/emails/province/round1_update.txt', {**self.base, **d})
                messages.append({'email': email, 'province_ids': [pid], 'to_names': sorted(entry['names']),
                                 'subject': f'{self.olympiad["name"]} I даваа: {d["province"]} — сургуулиудын бүртгэл, хамтын ажиллагааны хүсэлт',
                                 'body': body, 'html': text_to_html(body), 'attachment': self._xlsx(d)})
        return messages

    def _xlsx(self, d):
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        wb = Workbook()
        ws = wb.active
        ws.title = 'Сургуулиуд'
        ws.append([f'{d["province"]} — {self.today:%Y-%m-%d}-ны байдлаар. Анхаарал шаардлагатай сургуулиуд эхэнд.'])
        ws.append([])
        head = ['Сургууль', 'Анхаарах', 'Бүртгэлтэй сурагч (бүх жил)', 'Энэ жил бүртгэсэн', 'Батлагдаагүй хүсэлт', 'Бүртгэгч багш', 'Нэвтрэх нэр',
                'Имэйл', 'Утас', 'Сүүлд нэвтэрсэн', 'Удирдлагын имэйл', 'Утсаар холбогдсон (огноо)', 'Тэмдэглэл']
        ws.append(head)
        for c in ws[3]:
            c.font = Font(bold=True)
        red = PatternFill('solid', fgColor='F8CBAD')
        for r in sorted(d['rows'], key=lambda r: (not r['issues'], r['name'])):
            ws.append([r['name'], r['issue'], r['students'], r['new'], r['pending'], r['registrar'], r['username'], r['email'],
                       r['mobile'], r['last_login'], r['manager_email'], '', ''])
            if r['issues']:
                for c in ws[ws.max_row][:2]:
                    c.fill = red
        for col, w in zip('ABCDEFGHIJKLM', (30, 34, 12, 10, 10, 26, 16, 32, 12, 14, 32, 16, 30)):
            ws.column_dimensions[col].width = w
        ws.freeze_panes = 'A4'
        buf = io.BytesIO()
        wb.save(buf)
        name = re.sub(r'[^\w-]+', '_', d['province']).strip('_')
        return (f'{name}_sanguuliud_{self.today:%Y%m%d}.xlsx', buf.getvalue(),
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def _email(self, m, to, subject=None):
        msg = EmailMultiAlternatives(subject=subject or m['subject'], body=m['body'], from_email=FROM_EMAIL,
                                     to=[to], reply_to=[FROM_EMAIL])
        msg.attach_alternative(m['html'], 'text/html')
        msg.attach(*m['attachment'])
        return msg

    # ---------------------------------------------------------------- send

    def _log_dir(self):
        return os.path.join(settings.BASE_DIR, 'logs')

    def _already_sent(self):
        sent = set()
        for path in glob.glob(os.path.join(self._log_dir(), LOG_GLOB)):
            with open(path, newline='', encoding='utf-8-sig') as f:
                sent |= {norm_email(r['email']) for r in csv.DictReader(f) if r['status'] == 'sent'}
        return sent

    def _send_all(self, messages, opts):
        if not messages:
            self.stdout.write('Илгээх имэйл алга.')
            return
        if not opts['yes'] and input(f'{len(messages)} имэйл илгээх үү? [yes/no]: ').strip().lower() != 'yes':
            self.stdout.write('Цуцаллаа.')
            return
        os.makedirs(self._log_dir(), exist_ok=True)
        log_path = os.path.join(self._log_dir(), f'province_update_{timezone.localtime():%Y%m%d_%H%M%S}.csv')
        connection = get_connection()
        sent = failed = 0
        with open(log_path, 'w', newline='', encoding='utf-8') as f:
            log = csv.writer(f)
            log.writerow(['email', 'province_ids', 'status', 'message_id', 'error', 'time'])
            for m in messages:
                msg = self._email(m, m['email'])
                msg.connection = connection
                try:
                    msg.send()
                    status = getattr(msg, 'anymail_status', None)
                    log.writerow([m['email'], ' '.join(map(str, m['province_ids'])), 'sent',
                                  getattr(status, 'message_id', '') or '', '', timezone.now().isoformat()])
                    sent += 1
                except Exception as exc:
                    log.writerow([m['email'], ' '.join(map(str, m['province_ids'])), 'failed', '', str(exc)[:300],
                                  timezone.now().isoformat()])
                    failed += 1
                f.flush()
                time.sleep(1 / opts['rate'] if opts['rate'] > 0 else 0)
        self.stdout.write(self.style.SUCCESS(f'Илгээсэн: {sent}, алдаа: {failed}. Лог: {log_path}'))

    # ---------------------------------------------------------------- post

    def _update_post(self, data):
        from posts.models import Post
        post = Post.objects.get(pk=POST_ID)
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        backup = os.path.join(backup_dir, f'post{POST_ID}_descr_{timezone.localtime():%Y%m%d_%H%M%S}.html')
        with open(backup, 'w', encoding='utf-8') as f:
            f.write(post.descr or '')
        head = post.descr.split('<h4>Имэйл хүлээн авахгүй байгаа сургуулиуд')[0].split(POST_MARK)[0]
        n = sum(len(d['attention']) for d in data.values())
        parts = [f'{POST_MARK} ({n})</h4>',
                 f'<p><em>{self.today:%Y-%m-%d}-ны байдлаар шинэчилсэн. Жагсаалтыг тухай бүр шинэчилнэ.</em></p>',
                 '<p>Доорх сургуулиуд I даваанд бэлэн болоогүй байна: бүртгэгч багшгүй, бүртгэгч багшийн имэйл хүрэхгүй, '
                 'эсвэл сургуульд бүртгэлтэй сурагч огт байхгүй (өмнөх жилүүдийнхийг оруулаад). Аймаг, дүүргийн олимпиад хариуцсан мэргэжилтэн эсвэл '
                 '<a href="mailto:registration@mmo.mn">registration@mmo.mn</a> хаягаар холбогдоно уу.</p>',
                 '<table class="table table-bordered table-sm"><thead><tr><th>Аймаг/дүүрэг</th><th>Сургууль</th>'
                 '<th>Асуудал</th><th>Юу хийх вэ</th></tr></thead><tbody>']
        for d in sorted(data.values(), key=lambda d: d['province']):
            att = d['attention']
            for i, r in enumerate(att):
                cell = (f'<td rowspan="{len(att)}" style="vertical-align:top"><strong>{escape(d["province"])}</strong></td>'
                        if i == 0 else '')
                todo = '; '.join(ISSUE_ACTION[x] for x in r['issues'])
                parts.append(f'<tr>{cell}<td>{escape(r["name"])}</td><td>{escape(r["issue"])}</td><td>{escape(todo)}</td></tr>')
        parts.append('</tbody></table>')
        post.descr = head + '\n'.join(parts)
        post.save()
        self.stdout.write(self.style.SUCCESS(f'Пост {POST_ID} шинэчлэгдлээ: {n} сургууль. Хуучныг хадгалсан: {backup}'))
