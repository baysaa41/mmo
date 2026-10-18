"""
Багшаас registration@mmo.mn-д хариу болгон ирсэн Excel (ID, «Шинэ имэйл») файлаар сурагчдын имэйлийг солино.
Хувийн хуудсаар (schools/email_bulk) хийдэгтэй ижил шалгалтыг хэрэглэнэ.

Анхдагчаар юу ч өөрчлөхгүй (dry-run): төлөвлөгөө, татгалзсан мөр, багшид илгээх хариуны төслийг харуулна.
  python manage.py apply_email_replies --from teacher@gmail.com --file reply.xlsx
  python manage.py apply_email_replies --from teacher@gmail.com --file reply.xlsx --apply

--from нь багшид 5+ аккаунт бүртгэлтэй имэйл (илгээгчийн хаяг). Имэйлийн From толгойг хуурамчаар
бичиж болох тул хариуг зөвхөн webmail дээр харж, илгээгч нь манай илгээсэн хаягтай таарч байгааг нягтална уу.
"""
import csv
import os
from collections import Counter

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from schools import email_bulk as bulk
from schools.moderator import norm_email


class Command(BaseCommand):
    help = 'Багшийн хариу Excel-ээр сурагчдын имэйлийг солино (анхдагч dry-run).'

    def add_arguments(self, parser):
        parser.add_argument('--from', dest='sender', required=True, help='Хариу илгээсэн багшийн имэйл')
        parser.add_argument('--file', required=True, help='Хавсаргасан .xlsx файл')
        parser.add_argument('--apply', action='store_true', help='Бодитоор солино')
        parser.add_argument('--no-links', action='store_true', help='Нууц үгийн холбоос илгээхгүй')

    def handle(self, *args, **opts):
        email = norm_email(opts['sender'])
        accounts = list(User.objects.filter(email__iexact=email, is_active=True).order_by('id'))
        if not email or not accounts:
            raise CommandError(f'{opts["sender"]} имэйлтэй идэвхтэй аккаунт олдсонгүй.')
        anchor = accounts[0].pk  # round1_links.make_token-той ижил: хамгийн жижиг id
        self.stdout.write(f'Илгээгч: {email}, аккаунт: {len(accounts)}, anchor id: {anchor}')

        try:
            with open(opts['file'], 'rb') as f:
                plan = bulk.build_plan(email, anchor, f)
        except Exception as exc:
            raise CommandError(f'Файлыг уншиж чадсангүй: {exc}')

        changes, rejected = plan['changes'], plan['rejected']
        self.stdout.write(f'Солих: {len(changes)}, татгалзсан: {len(rejected)}, хоосон (өөрчлөхгүй): {plan["unchanged"]}')
        for reason, n in Counter(r[3] for r in rejected).most_common():
            self.stdout.write(f'  {n:4}  {reason}')
        for uid, old, new, label in changes[:15]:
            self.stdout.write(f'  {uid} {label}: {old} → {new}')
        if len(changes) > 15:
            self.stdout.write(f'  ... мөн {len(changes) - 15}')

        done = []
        if opts['apply']:
            if not changes:
                self.stdout.write('Солих зүйл алга.')
            else:
                done, late_rejected = bulk.apply_changes(email, anchor, [(c[0], c[2]) for c in changes])
                self.stdout.write(self.style.SUCCESS(f'Солигдсон: {len(done)}, баталгаажуулахад татгалзсан: {len(late_rejected)}'))
                if done and not opts['no_links']:
                    from schools.tasks import send_email_change_links_task
                    send_email_change_links_task.delay(done)
                    self.stdout.write('Нууц үгийн холбоог celery-ээр илгээж байна.')
        else:
            self.stdout.write(self.style.WARNING('Dry-run: юу ч өөрчлөөгүй. --apply-аар солино.'))

        path = self._write_reply(email, accounts[0], len(changes) if not opts['apply'] else len(done), rejected, opts['apply'])
        self.stdout.write(f'Багшид илгээх хариуны төсөл: {path}')

    def _write_reply(self, email, user, count, rejected, applied):
        name = user.get_full_name().strip() or user.username
        lines = [f'Сайн байна уу, {name}.', '',
                 (f'Таны илгээсэн файлаар {count} сурагчийн имэйлийг солилоо. Сурагч бүрийн шинэ имэйл рүү '
                  'нууц үгээ тохируулах холбоос явсан.') if applied else
                 f'Таны файлыг шалгалаа: {count} сурагчийн имэйлийг солихоор бэлэн боллоо.']
        if rejected:
            lines += ['', f'Дараах {len(rejected)} мөрийг солиогүй:']
            lines += [f'  • {r[1]} — {r[2]}: {r[3]}' for r in rejected[:100]]
            if len(rejected) > 100:
                lines.append(f'  ... мөн {len(rejected) - 100} мөр')
            lines += ['', 'Эдгээрийг засаад файлаа дахин илгээж болно.']
        lines += ['', 'Математикийн олимпиадын хороо']
        log_dir = os.path.join(settings.BASE_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, f'email_reply_{email.replace("@", "_at_")}_{timezone.localtime():%Y%m%d_%H%M%S}.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        return path
