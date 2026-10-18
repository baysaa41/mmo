"""
ММО-63 I давааны мэдээллийн имэйл (энгийн хувилбар: 1–4 аккаунттай хаяг). Нэг хаяг руу нэг л имэйл
явна; хаяг бүрт хувийн хуудас (`/schools/r1/<token>/`) болон List-Unsubscribe толгой орно.

Бүртгэгч багш, сургуулийн удирдлага, аймгийн админ (Сануулгын хүлээн авагчид) болон 5+ аккаунттай
багш нарыг энд оруулахгүй — тэдэнд тусдаа имэйл явна.

Анхдагчаар юу ч илгээхгүй — тоо ба жишээ харуулна.
  python manage.py send_round1_info
  python manage.py send_round1_info --test-email me@example.com
  python manage.py send_round1_info --send --limit 500
  python manage.py send_round1_info --teachers --test-email me@example.com
  python manage.py send_round1_info --registrars --test-email me@example.com

--teachers: 5+ аккаунттай хаяг (олон сурагчаа өөрийн имэйлээр бүртгүүлсэн багш нар, #38). Тэдэнд
«хүн бүр өөрийн хаягаар бүртгүүлэх» бодлогын тайлбар болон id/нэр/сургууль/анги/хоосон «шинэ имэйл»
баганатай Excel хавсаргана.
"""
import csv
import io
import os
import time
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from emails.html import text_to_html
from olympiad.models import Olympiad, SchoolYear
from schools import round1_links as links
from schools.campaign_blacklist import campaign_blocked_emails
from schools import enrollment
from schools.models import School
from schools.moderator import NOTICE_FROM_EMAIL as FROM_EMAIL, norm_email

MAX_ACCOUNTS = 4  # үүнээс олон аккаунттай хаяг = олон сурагч бүртгүүлсэн багш (#38)
MAX_ROWS = 4
CHUNK = 500
# Багш, комисс зэрэг сурагч биш аккаунтуудыг энэ имэйлд оруулахгүй (Дэмжигч = эцэг эх орно)
NON_STUDENT_GRADES = ['Багш', 'Комисс', 'БСУГ мэргэжилтэн']
STATUS_TEXT = {
    links.REGISTERED: 'I даваанд бүртгэлтэй',
    links.REQUESTED: 'бүртгэлийн хүсэлт илгээсэн, багшийн баталгаа хүлээж байна',
    links.NOT_REGISTERED: 'сургуулийн бүртгэгч багш дээр бүртгэлгүй',
    links.NO_SCHOOL: 'сургууль сонгоогүй',
}


def display_name(user):
    return user.get_full_name().strip() or user.username


class Command(BaseCommand):
    help = 'ММО-63 I давааны мэдээллийн имэйлийг (1–4 аккаунттай хаяг) илгээнэ.'

    def add_arguments(self, parser):
        parser.add_argument('--active-days', type=int, default=365,
                            help='Сүүлийн N хоногт нэвтэрсэн/идэвхтэй аккаунттай хаяг (анхдагч 365). 0 = бүгд')
        parser.add_argument('--inactive-only', action='store_true',
                            help='Зөвхөн --active-days-аас өмнө нь идэвхтэй байсан (2-р үе)')
        parser.add_argument('--teachers', action='store_true',
                            help='Зөвхөн 5+ аккаунттай хаяг (багш нар): бодлогын тайлбар + Excel хавсралт')
        parser.add_argument('--registrars', action='store_true',
                            help='Сургуулийн бүртгэгч багш нар (School.user): хүсэлт шийдэх, жагсаалт шалгах заавар (#33)')
        parser.add_argument('--limit', type=int, help='Дээд тал нь N имэйл (үе шаттай илгээхэд)')
        parser.add_argument('--skip-log', nargs='+', default=[],
                            help='Өмнөх ажиллагааны лог(ууд) — "sent" болсон хаягуудад дахин илгээхгүй')
        parser.add_argument('--test-email', help='Хэд хэдэн төрлийн жишээг зөвхөн энэ хаяг руу илгээнэ')
        parser.add_argument('--send', action='store_true', help='Бодитоор илгээнэ')
        parser.add_argument('--yes', action='store_true', help='--send үед баталгаажуулалт асуухгүй')
        parser.add_argument('--rate', type=float, default=10, help='Секундэд илгээх дээд тоо')
        parser.add_argument('--show', type=int, default=2, help='Урьдчилан харах жишээний тоо')

    def handle(self, *args, **opts):
        today = timezone.localdate()
        sy = SchoolYear.objects.filter(start__lte=today, end__gte=today).first()
        if not sy:
            raise CommandError('Өнөөдрийг агуулсан хичээлийн жил олдсонгүй.')
        self.olympiads = list(Olympiad.objects.filter(school_year=sy, round=1)
                              .select_related('level').order_by('level__name'))
        if not self.olympiads:
            raise CommandError(f'{sy} хичээлийн жилд I давааны олимпиад алга.')
        site = settings.SITE_URL.rstrip('/')
        self.base = {
            'site': site, 'from_email': FROM_EMAIL,
            'olympiad': self._olympiad_info(),
            'guideline_url': f'{site}/post/?id={sy.guideline_post_id}' if sy.guideline_post_id else None,
        }
        self.teachers = opts['teachers']
        self.registrars = opts['registrars']
        if self.teachers and self.registrars:
            raise CommandError('--teachers болон --registrars хамт хэрэглэхгүй.')
        prefix = f'{self.olympiads[0].name.split(",")[0]} I даваа'
        self.subject = (f'{prefix}: сурагчдын бүртгэлийн хүсэлт, жагсаалтаа шалгана уу' if self.registrars else
                        f'{prefix}: сурагчдаа өөрсдийн имэйлээр бүртгүүлэх тухай' if self.teachers
                        else f'{prefix}: мэдээллээ шалгаж, бүртгэлээ баталгаажуулна уу')

        self.stdout.write('Хар жагсаалт бэлдэж байна (SES suppression орно)...')
        self.excluded = campaign_blocked_emails() | self._already_sent(opts['skip_log'])
        if not self.registrars:
            self.excluded |= self._official_emails()
        groups = self._registrar_audience() if self.registrars else self._audience(opts)
        total = len(groups)
        if opts['limit']:
            groups = dict(list(groups.items())[:opts['limit']])
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'{self.subject} | илгээгч: {FROM_EMAIL}\n'
            f'  Хаяг: {total}, энэ удаа: {len(groups)}, нийт аккаунт: {sum(len(v) for v in groups.values())}'))

        if opts['test_email']:
            self._send_test(groups, opts['test_email'])
        elif opts['send']:
            self._send_all(groups, opts)
        else:
            self._preview(groups, opts['show'])

    # --------------------------------------------------------------- audience

    def _olympiad_info(self):
        weekdays = ['Даваа', 'Мягмар', 'Лхагва', 'Пүрэв', 'Баасан', 'Бямба', 'Ням']
        starts = sorted({timezone.localtime(o.start_time).date() for o in self.olympiads if o.start_time})
        date = ', '.join(f'{d.year} оны {d.month}-р сарын {d.day}-ны өдөр ({weekdays[d.weekday()]} гараг)'
                         for d in starts)
        levels = ', '.join(o.level.name.replace('-', '–') for o in self.olympiads) + ' анги'
        return {'name': self.olympiads[0].name.split(',')[0], 'date': date or 'тодорхойгүй', 'levels_display': levels}

    def _official_emails(self):
        """Сануулгын хүлээн авагчид (бүртгэгч багш, удирдлага, аймгийн админ) — тусдаа имэйл авна."""
        emails = set()
        for s in School.objects.select_related('user', 'manager'):
            emails |= {norm_email(u.email) for u in (s.user, s.manager) if u}
        return emails - {''}

    def _registrar_audience(self):
        """{email: [school_id, ...]} — School.user-ийн имэйлээр бүлэглэсэн."""
        groups = defaultdict(list)
        for s in School.objects.filter(user__is_active=True).exclude(name='Бусад').select_related('user').order_by('province__name', 'name'):
            e = norm_email(s.user.email)
            if e and e not in self.excluded:
                groups[e].append(s.pk)
        return dict(groups)

    def _already_sent(self, paths):
        sent = set()
        for path in paths:
            with open(path, newline='', encoding='utf-8-sig') as f:
                sent |= {row['email'] for row in csv.DictReader(f) if row['status'] == 'sent'}
        return sent

    def _audience(self, opts):
        """{email: [user_id, ...]} — id-аар эрэмбэлсэн, 1–MAX_ACCOUNTS аккаунттай, илгээж болох хаягууд."""
        users = (User.objects.filter(is_active=True).exclude(email='')
                 .exclude(email__iendswith='@mmo.mn').exclude(data__grade__name__in=NON_STUDENT_GRADES))
        if self.teachers:  # нэргүй хоосон аккаунтыг тоолохгүй, Excel-д оруулахгүй
            users = users.exclude(first_name='', last_name='')
        by_email = defaultdict(list)
        for uid, email in users.order_by('id').values_list('id', 'email'):
            e = norm_email(email)
            if e and e not in self.excluded:
                by_email[e].append(uid)
        if opts['active_days']:
            since = timezone.now() - timedelta(days=opts['active_days'])
            active = set(users.filter(Q(last_login__gte=since) | Q(data__last_activity__gte=since))
                         .values_list('id', flat=True))
        else:
            active = None
        groups = {}
        for e, ids in by_email.items():
            if (len(ids) > MAX_ACCOUNTS) != self.teachers:
                continue
            if active is not None and bool(active.intersection(ids)) == opts['inactive_only']:
                continue
            groups[e] = ids
        return groups

    # ---------------------------------------------------------------- message

    def _registrar_messages(self, groups):
        for email, school_ids in groups.items():
            schools = list(School.objects.filter(pk__in=school_ids).select_related('user', 'province').order_by('name'))
            rows = [{'name': sc.name, 'province': sc.province.name if sc.province else '',
                     'registered': sc.group.user_set.count() if sc.group_id else 0,
                     'pending': enrollment.pending_students(sc).count(),
                     'url': f'{self.base["site"]}{reverse("school_all_users", args=[sc.pk])}'} for sc in schools]
            user = schools[0].user
            context = {**self.base, 'name': display_name(user), 'schools': rows[:10], 'hidden': max(0, len(rows) - 10),
                       'login_url': f'{self.base["site"]}/accounts/login/'}
            body = render_to_string('schools/emails/round1/registrar.txt', context)
            yield {'email': email, 'user_ids': [user.pk], 'body': body, 'html': text_to_html(body), 'unsubscribe': None}

    def _messages(self, groups):
        """(email, user_ids) -> бэлэн имэйлүүд, CHUNK-аар query хийнэ."""
        if self.registrars:
            yield from self._registrar_messages(groups)
            return
        items = list(groups.items())
        for i in range(0, len(items), CHUNK):
            chunk = items[i:i + CHUNK]
            ids = [uid for _e, uids in chunk for uid in uids]
            users = {u.pk: u for u in User.objects.filter(pk__in=ids).select_related(
                'data__school__user', 'data__school__province', 'data__grade')}
            status = dict((u.pk, s) for u, s in links.account_rows(users.values()))
            for email, uids in chunk:
                yield self._build(email, [users[u] for u in uids], status)

    def _build(self, email, users, status):
        if self.teachers:
            return self._build_teacher(email, users, status)
        rows = [{'name': display_name(u), 'grade': getattr(getattr(getattr(u, 'data', None), 'grade', None), 'name', '') or '',
                 'status': self._status_text(u, status[u.pk])} for u in users[:MAX_ROWS]]
        first = users[0]
        name = display_name(first) if len(users) == 1 else f'{first.first_name or display_name(first)} (+{len(users) - 1} хүн)'
        token = links.token_for_uid(first.pk)
        link = f'{self.base["site"]}{reverse("round1_info", args=[token])}'
        unsubscribe = f'{self.base["site"]}{reverse("round1_unsubscribe", args=[token])}'
        context = {**self.base, 'name': name, 'rows': rows, 'hidden': len(users) - len(rows), 'link': link,
                   'unsubscribe_url': unsubscribe, 'needs_action': any(status[u.pk] == links.NOT_REGISTERED for u in users)}
        body = render_to_string('schools/emails/round1/info.txt', context)
        return {'email': email, 'user_ids': [u.pk for u in users], 'body': body, 'html': text_to_html(body),
                'unsubscribe': unsubscribe}

    def _build_teacher(self, email, users, status):
        counts = defaultdict(int)
        for u in users:
            counts[status[u.pk]] += 1
        first = users[0]
        token = links.token_for_uid(first.pk)
        link = f'{self.base["site"]}{reverse("round1_info", args=[token])}'
        context = {**self.base, 'name': display_name(first), 'total': len(users), 'link': link,
                   'unsubscribe_url': f'{self.base["site"]}{reverse("round1_unsubscribe", args=[token])}',
                   'registered': counts[links.REGISTERED], 'not_registered': counts[links.NOT_REGISTERED],
                   'requested': counts[links.REQUESTED], 'no_school': counts[links.NO_SCHOOL]}
        body = render_to_string('schools/emails/round1/teacher.txt', context)
        return {'email': email, 'user_ids': [u.pk for u in users], 'body': body, 'html': text_to_html(body),
                'unsubscribe': context['unsubscribe_url'], 'attachment': self._students_xlsx(users)}

    def _students_xlsx(self, users):
        """id, нэр, сургууль, анги, хоосон «Шинэ имэйл» — багш бөглөөд registration@mmo.mn руу буцаана."""
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = 'Сурагчид'
        ws.append(['ID', 'Овог', 'Нэр', 'Сургууль', 'Анги', 'Шинэ имэйл'])
        for u in users:
            meta = getattr(u, 'data', None)
            ws.append([u.pk, u.last_name, u.first_name, getattr(getattr(meta, 'school', None), 'name', '') or '',
                       getattr(getattr(meta, 'grade', None), 'name', '') or '', ''])
        for col, width in zip('ABCDEF', (10, 18, 18, 36, 12, 32)):
            ws.column_dimensions[col].width = width
        ws.freeze_panes = 'A2'
        buf = io.BytesIO()
        wb.save(buf)
        return ('surguudiin_jagsaalt.xlsx', buf.getvalue(),
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def _status_text(self, user, status):
        text = STATUS_TEXT[status]
        school = getattr(getattr(user, 'data', None), 'school', None)
        if school and status in (links.REGISTERED, links.NOT_REGISTERED):
            return f'{school.name}: {text}' if status == links.REGISTERED else f'{school.name} — {text}'
        return text

    def _email(self, m, to, subject=None):
        from django.core.mail import EmailMultiAlternatives
        msg = EmailMultiAlternatives(
            subject=subject or self.subject, body=m['body'], from_email=FROM_EMAIL, to=[to], reply_to=[FROM_EMAIL],
            headers=({'List-Unsubscribe': f'<{m["unsubscribe"]}>', 'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'}
                     if m['unsubscribe'] else {}))
        msg.attach_alternative(m['html'], 'text/html')
        if m.get('attachment'):
            msg.attach(*m['attachment'])
        return msg

    # ----------------------------------------------------------------- output

    def _preview(self, groups, show):
        for m in list(self._messages(dict(list(groups.items())[:show]))):
            self.stdout.write('=' * 72)
            self.stdout.write(f'To: {m["email"]}\nSubject: {self.subject}\n{"-" * 72}\n{m["body"]}')
        self.stdout.write(self.style.WARNING('\nЮу ч илгээгээгүй. --test-email эсвэл --send ашиглана уу.'))

    def _send_test(self, groups, to):
        """Нэг аккаунттай, олон аккаунттай, бүртгэлгүй төрлөөс жишээ."""
        samples, seen = [], set()
        for m in self._messages(dict(list(groups.items())[:3000])):
            kind = (len(m['user_ids']) > 1, 'Бүртгэгч багш дээр бүртгэлгүй' in m['body'] or 'бүртгэлгүй' in m['body'])
            if kind not in seen:
                seen.add(kind)
                samples.append(m)
        for m in samples:
            self._email(m, to, f'[ТЕСТ → {m["email"]}] {self.subject}').send()
            self.stdout.write(self.style.SUCCESS(f'Тест ({len(m["user_ids"])} аккаунт) илгээлээ → {to}'))

    def _send_all(self, groups, opts):
        if not groups:
            self.stdout.write('Илгээх имэйл алга.')
            return
        if not opts['yes']:
            if input(f'{len(groups)} имэйлийг {FROM_EMAIL} хаягаас илгээх үү? [yes/no]: ').strip().lower() != 'yes':
                self.stdout.write('Цуцаллаа.')
                return
        log_dir = os.path.join(settings.BASE_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f'round1_info_{timezone.localtime():%Y%m%d_%H%M%S}.csv')
        interval = 1 / opts['rate'] if opts['rate'] > 0 else 0
        sent = failed = 0
        from django.core.mail import get_connection
        connection = get_connection()
        with open(log_path, 'w', newline='', encoding='utf-8') as f:
            log = csv.writer(f)
            log.writerow(['email', 'user_ids', 'status', 'message_id', 'error', 'time'])
            for i, m in enumerate(self._messages(groups), 1):
                msg = self._email(m, m['email'])
                msg.connection = connection
                ids = ' '.join(map(str, m['user_ids']))
                try:
                    msg.send()
                    status = getattr(msg, 'anymail_status', None)
                    log.writerow([m['email'], ids, 'sent', getattr(status, 'message_id', '') or '', '',
                                  timezone.now().isoformat()])
                    sent += 1
                except Exception as exc:
                    log.writerow([m['email'], ids, 'failed', '', str(exc)[:300], timezone.now().isoformat()])
                    failed += 1
                f.flush()
                if i % 100 == 0:
                    self.stdout.write(f'  {i}/{len(groups)}...')
                time.sleep(interval)
        self.stdout.write(self.style.SUCCESS(f'Илгээсэн: {sent}, алдаа: {failed}. Лог: {log_path}'))
        if failed:
            self.stdout.write(f'Алдаатайг дахин илгээх: --send --skip-log {log_path}')
