from datetime import date

from django.core.management.base import BaseCommand

from accounts.models import Province
from olympiad.models import SchoolYear
from olympiad.utils.round2_quota import school_round2_quota_totals, school_round2_quota_totals_key
from django.core.cache import cache


class Command(BaseCommand):
    help = (
        'Сургууль бүрээс аймаг/дүүргийн олимпиадад (round=2) шалгарах сурагчийн тоог '
        'бүх аймаг, дүүрэгт тооцоолж кэшлэнэ (сургуулийн бүртгэлийн хуудас харуулдаг). '
        'Нэг аймаг ~4-9 сек, бүгд ~2 минут.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, help='SchoolYear ID (default: идэвхтэй хичээлийн жил)')
        parser.add_argument('--refresh', action='store_true', help='Кэшлэгдсэн утгыг дахин тооцно')

    def handle(self, *args, **options):
        if options['year']:
            year = SchoolYear.objects.filter(pk=options['year']).first()
        else:
            today = date.today()
            year = SchoolYear.objects.filter(start__lte=today, end__gte=today).first()
        if not year:
            self.stderr.write('Хичээлийн жил олдсонгүй.')
            return
        count = 0
        for province in Province.objects.order_by('id'):
            if options['refresh']:
                cache.delete(school_round2_quota_totals_key(year.id, province.id))
            totals = school_round2_quota_totals(province, year)
            count += len(totals)
            self.stdout.write(f'{province.name}: {len(totals)} сургууль')
        self.stdout.write(self.style.SUCCESS(f'{year.name}: нийт {count} сургуулийн тоо кэшлэгдлээ.'))
