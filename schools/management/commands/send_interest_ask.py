"""
Сонирхол асуух имэйл: «ММО / бусад олимпиад / MathMinds (mathminds.club)-ийн мэдээллийг авах уу?»
Хариуг UserMeta.wants_* талбарт хадгална (холбоос: /schools/i/<token>/). Цаашдын зар сурталчилгааг
зөвхөн «тийм» гэсэн хаягуудад явуулна (schools.round1_links.promo_emails).

Нэг хаяг руу нэг л имэйл. Давхардлаас автоматаар сэргийлнэ:
  - өмнөх logs/interest_ask_*.csv-д «sent» болсон хаяг
  - сонирхлоо өмнө нь хадгалсан (wants_* null биш) аккаунттай хаяг
  - unsubscribe хийсэн, хар жагсаалтад (bounce/complaint/SES suppression) орсон хаяг

Анхдагчаар юу ч илгээхгүй — тоо ба жишээ харуулна.
  python manage.py send_interest_ask
  python manage.py send_interest_ask --test-email me@example.com   # өөрийн аккаунтын мэдээллээр
  python manage.py send_interest_ask --send --limit 500
"""
import csv
import glob
import os
import time
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from emails.html import text_to_html
from schools import round1_links as links
from schools.campaign_blacklist import campaign_blocked_emails
from schools.management.commands.send_round1_info import display_name
from schools.moderator import NOTICE_FROM_EMAIL as FROM_EMAIL, norm_email

SUBJECT = 'Танд ямар мэдээлэл хүргэх вэ?'
LOG_GLOB = 'interest_ask_*.csv'
CHUNK = 500


class Command(BaseCommand):
    help = 'Сонирхол асуух имэйлийг (нэг хаяг = нэг имэйл) илгээнэ.'

    def add_arguments(self, parser):
        parser.add_argument('--active-days', type=int, default=365,
                            help='Сүүлийн N хоногт нэвтэрсэн/идэвхтэй аккаунттай хаяг (анхдагч 365). 0 = бүгд')
        parser.add_argument('--inactive-min-days', type=int, default=0,
                            help='Сүүлийн N хоногт нэвтрээгүй/идэвхгүй хаяг ЛЮ (аккаунт бүр N хоногоос өмнө). '
                                 '--active-days 0-тэй хамт: «N хоногоос дээш хугацаанд идэвхгүй» давалгаа')
        parser.add_argument('--limit', type=int, help='Дээд тал нь N имэйл (үе шаттай илгээхэд)')
        parser.add_argument('--skip-log', nargs='+', default=[], help='Нэмэлт лог(ууд) — "sent" хаягуудад илгээхгүй')
        parser.add_argument('--no-ses', action='store_true', help='SES suppression list-ийг уншихгүй (зөвхөн dry-run-д)')
        parser.add_argument('--test-email', help='Зөвхөн энэ хаяг руу, ӨӨРИЙН аккаунтын мэдээллээр тест илгээнэ')
        parser.add_argument('--send', action='store_true', help='Бодитоор илгээнэ')
        parser.add_argument('--yes', action='store_true', help='--send үед баталгаажуулалт асуухгүй')
        parser.add_argument('--rate', type=float, default=10, help='Секундэд илгээх дээд тоо')
        parser.add_argument('--show', type=int, default=2, help='Урьдчилан харах жишээний тоо')

    # -------------------------------------------------------------- audience

    def _log_dir(self):
        return os.path.join(settings.BASE_DIR, 'logs')

    def _already_sent(self, extra):
        """Өмнөх бүх interest_ask лог + --skip-log-д «sent» болсон хаягууд."""
        sent = set()
        for path in glob.glob(os.path.join(self._log_dir(), LOG_GLOB)) + list(extra):
            with open(path, newline='', encoding='utf-8-sig') as f:
                sent |= {norm_email(r['email']) for r in csv.DictReader(f) if r['status'] == 'sent'}
        return sent

    def _excluded(self, opts):
        from emails.models import EmailUnsubscribe
        excluded = campaign_blocked_emails(with_ses=not opts['no_ses'])
        excluded |= {norm_email(e) for e in EmailUnsubscribe.objects.values_list('email', flat=True)}
        return (excluded | self._already_sent(opts['skip_log'])) - {''}

    def _audience(self, opts):
        """{email: [user_id, ...]} — id-аар эрэмбэлсэн, сонирхлоо хадгалаагүй, илгээж болох хаягууд."""
        users = User.objects.filter(is_active=True).exclude(email='').exclude(email__iendswith='@mmo.mn')
        excluded = self._excluded(opts)
        by_email = defaultdict(list)
        for uid, email in users.order_by('id').values_list('id', 'email'):
            e = norm_email(email)
            if e and e not in excluded:
                by_email[e].append(uid)
        answered = set(norm_email(e) for e in users.filter(data__interests_updated_at__isnull=False)
                       .values_list('email', flat=True))
        active = None
        if opts['active_days']:
            since = timezone.now() - timedelta(days=opts['active_days'])
            active = set(users.filter(Q(last_login__gte=since) | Q(data__last_activity__gte=since))
                         .values_list('id', flat=True))
        recent = None
        if opts['inactive_min_days']:
            since = timezone.now() - timedelta(days=opts['inactive_min_days'])
            recent = set(users.filter(Q(last_login__gte=since) | Q(data__last_activity__gte=since))
                         .values_list('id', flat=True))
        groups = {}
        for e, ids in by_email.items():
            if e in answered or (active is not None and not active.intersection(ids)):
                continue
            if recent is not None and recent.intersection(ids):
                continue
            groups[e] = ids
        return groups

    # --------------------------------------------------------------- message

    def _message(self, email, users):
        first = users[0]
        name = display_name(first) if len(users) == 1 else ''  # олон аккаунттай хаяг: эцэг эх, багш — нэр дурдахгүй
        token = links.token_for_uid(first.pk)
        site = settings.SITE_URL.rstrip('/')
        link = f'{site}{reverse("round1_interests", args=[token])}'
        unsubscribe = f'{site}{reverse("round1_unsubscribe", args=[token])}'
        body = render_to_string('schools/emails/round1/interests.txt', {
            'name': name, 'accounts': len(users), 'link': link, 'unsubscribe_url': unsubscribe, 'from_email': FROM_EMAIL})
        return {'email': email, 'user_ids': [u.pk for u in users], 'body': body, 'html': text_to_html(body),
                'unsubscribe': unsubscribe}

    def _messages(self, groups):
        items = list(groups.items())
        for i in range(0, len(items), CHUNK):
            chunk = items[i:i + CHUNK]
            users = {u.pk: u for u in User.objects.filter(pk__in=[uid for _e, ids in chunk for uid in ids])}
            for email, ids in chunk:
                yield self._message(email, [users[u] for u in ids])

    def _email(self, m, to, subject=SUBJECT):
        msg = EmailMultiAlternatives(
            subject=subject, body=m['body'], from_email=FROM_EMAIL, to=[to], reply_to=[FROM_EMAIL],
            headers={'List-Unsubscribe': f'<{m["unsubscribe"]}>', 'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'})
        msg.attach_alternative(m['html'], 'text/html')
        return msg

    # ---------------------------------------------------------------- output

    def handle(self, *args, **opts):
        if opts['test_email']:
            return self._send_test(opts['test_email'])
        groups = self._audience(opts)
        total = len(groups)
        if opts['limit']:
            groups = dict(list(groups.items())[:opts['limit']])
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'{SUBJECT} | илгээгч: {FROM_EMAIL}\n  Хаяг: {total}, энэ удаа: {len(groups)}, '
            f'нийт аккаунт: {sum(len(v) for v in groups.values())}'))
        if opts['send']:
            self._send_all(groups, opts)
        else:
            for m in list(self._messages(dict(list(groups.items())[:opts['show']]))):
                self.stdout.write('=' * 72)
                self.stdout.write(f'To: {m["email"]}\nSubject: {SUBJECT}\n{"-" * 72}\n{m["body"]}')
            self.stdout.write(self.style.WARNING('\nЮу ч илгээгээгүй. --test-email эсвэл --send ашиглана уу.'))

    def _send_test(self, to):
        """Тестийн хаягийн ӨӨРИЙН аккаунтаар — холбоосыг дарж хадгалсан ч бусдын мэдээлэл өөрчлөгдөхгүй."""
        users = list(links.accounts_for_email(to)[:5])
        if not users:
            raise CommandError(f'{to} хаягтай идэвхтэй аккаунт алга — тест илгээхгүй (бусдын токен ашиглахгүй).')
        m = self._message(norm_email(to), users)
        self._email(m, to, f'[ТЕСТ] {SUBJECT}').send()
        self.stdout.write(self.style.SUCCESS(f'Тест илгээлээ → {to} ({len(users)} аккаунт). Лог бичигдээгүй.'))

    def _send_all(self, groups, opts):
        if not groups:
            self.stdout.write('Илгээх имэйл алга.')
            return
        if not opts['yes'] and input(f'{len(groups)} имэйлийг {FROM_EMAIL} хаягаас илгээх үү? [yes/no]: ').strip().lower() != 'yes':
            self.stdout.write('Цуцаллаа.')
            return
        os.makedirs(self._log_dir(), exist_ok=True)
        log_path = os.path.join(self._log_dir(), f'interest_ask_{timezone.localtime():%Y%m%d_%H%M%S}.csv')
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
                    log.writerow([m['email'], ids, 'sent', getattr(status, 'message_id', '') or '', '', timezone.now().isoformat()])
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
            self.stdout.write('Алдаатайг дахин илгээхэд лог автоматаар уншигдана — зөвхөн «sent» хаягууд алгасагдана.')
