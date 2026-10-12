"""
I давааны имэйл кампанит ажлын хар жагсаалт ба хүлээн авагчдын тоо (юу ч илгээхгүй, өөрчлөхгүй).

  python manage.py round1_audience
  python manage.py round1_audience --no-ses --csv /tmp/blacklist.csv
"""
import csv
from collections import Counter
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Q
from django.core.management.base import BaseCommand
from django.utils import timezone

from schools.campaign_blacklist import campaign_blacklist
from schools.moderator import norm_email

MANY_ACCOUNTS = 5  # үүнээс олон аккаунттай хаяг = олон сурагч бүртгүүлсэн багш


class Command(BaseCommand):
    help = 'I давааны кампанит ажлын хар жагсаалт, үе шат тус бүрийн хүлээн авагчдын тоо (dry-run)'

    def add_arguments(self, parser):
        parser.add_argument('--no-ses', action='store_true', help='SES suppression list-ийг уншихгүй')
        parser.add_argument('--active-days', type=int, default=365, help='1-р үеийн нэвтэрсэн хугацаа (хоног)')
        parser.add_argument('--csv', help='Хар жагсаалтыг (email, шалтгаанууд) CSV-д бичих')

    def handle(self, *args, **opts):
        sources = campaign_blacklist(with_ses=not opts['no_ses'])
        blacklist = set().union(*sources.values())
        self.stdout.write('Хар жагсаалт (шалтгаан тус бүр, давхцалтай):')
        for name, emails in sources.items():
            self.stdout.write(f'  {name:15} {len(emails):6}')
        self.stdout.write(f'  {"НИЙТ":15} {len(blacklist):6}')

        users = User.objects.filter(is_active=True).exclude(email='')
        accounts = Counter(norm_email(e) for e in users.values_list('email', flat=True))
        invalid = accounts.pop('', 0)
        sendable = {e for e in accounts if e not in blacklist}
        since = timezone.now() - timedelta(days=opts['active_days'])
        active = {norm_email(e) for e in users.filter(Q(last_login__gte=since) | Q(data__last_activity__gte=since)).values_list('email', flat=True)}

        def row(label, emails):
            many = sum(1 for e in emails if accounts[e] >= MANY_ACCOUNTS)
            self.stdout.write(f'  {label:32} {len(emails):6} хаяг  {sum(accounts[e] for e in emails):7} аккаунт'
                              f'  ({MANY_ACCOUNTS}+ аккаунттай {many})')

        self.stdout.write(f'\nИдэвхтэй аккаунтын хаяг: {len(accounts)} (буруу/хоосон формат {invalid} аккаунт)')
        row('Илгээж болох', sendable)
        row(f'1-р үе (сүүлийн {opts["active_days"]} хоногт нэвтэрсэн)', sendable & active)
        row('2-р үе (үлдсэн)', sendable - active)

        if opts['csv']:
            with open(opts['csv'], 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['email', 'reasons'])
                for e in sorted(blacklist):
                    w.writerow([e, ' '.join(n for n, s in sources.items() if e in s)])
            self.stdout.write(f'\nCSV: {opts["csv"]}')
