from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = (
        'Spam/bot бүртгэлийн шинж чанартай хэрэглэгчдийг (идэвхжүүлээгүй, '
        'хэзээ ч нэвтрээгүй, профайл бөглөөгүй) олж устгана. Олимпиадад '
        'ямар нэгэн байдлаар оролцсон хэрэглэгчийг хэзээ ч устгахгүй.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Хамгийн багадаа хэдэн өдрийн өмнө бүртгүүлсэн байх ёстойг зааж өгнө '
                 '(идэвхжүүлэх линк дуусах хугацаа). Анхны утга: 7.'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Устгахгүйгээр зөвхөн тайлан харуулна.'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Баталгаажуулах "USTGAH" бичих шаардлагыг алгасна (автоматжуулсан скриптэд).'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        confirm = options['confirm']

        cutoff_date = timezone.now() - timedelta(days=days)

        # Spam хэрэглэгчийн шинж чанар:
        # 1. Идэвхжүүлээгүй (имэйл линк дараагүй)
        # 2. Хэзээ ч нэвтэрч байгаагүй
        # 3. Staff/superuser биш
        # 4. Идэвхжүүлэх линкийн хугацаа аль хэдийн дууссан (cutoff-оос өмнө бүртгүүлсэн)
        # 5. Аюулгүйн хатуу нөхцөл: олимпиадад ямар нэгэн байдлаар оролцоогүй
        #    (Result эсвэл ScoreSheet холбоотой бол хэзээ ч устгахгүй)
        spam_users = User.objects.filter(
            is_active=False,
            is_staff=False,
            is_superuser=False,
            last_login__isnull=True,
            date_joined__lt=cutoff_date,
        ).exclude(
            contest_results__isnull=False
        ).exclude(
            results__isnull=False
        ).distinct()

        user_count = spam_users.count()

        if user_count == 0:
            self.stdout.write(self.style.SUCCESS('Spam шинжтэй хэрэглэгч олдсонгүй.'))
            return

        self.stdout.write(self.style.WARNING(
            f'\n{cutoff_date.strftime("%Y-%m-%d")}-ээс өмнө бүртгүүлсэн, идэвхжүүлээгүй, '
            f'нэвтэрч байгаагүй, олимпиадад оролцоогүй {user_count} хэрэглэгч олдлоо.\n'
        ))

        preview = spam_users.order_by('date_joined')[:10]
        for user in preview:
            self.stdout.write(f'  ID: {user.id} | {user.username} | {user.email} | {user.date_joined:%Y-%m-%d}')
        if user_count > 10:
            self.stdout.write(f'  ... болон дахин {user_count - 10} хэрэглэгч')

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'\n--dry-run горим: {user_count} хэрэглэгч устгагдахгүй байна.'))
            return

        if not confirm:
            self.stdout.write(self.style.WARNING(
                f'\n⚠️  АНХААР: Энэ үйлдэл {user_count} хэрэглэгчийг '
                'ЭРГҮҮЛЭХ БОЛОМЖГҮЙ устгана!'
            ))
            confirmation = input('\nҮргэлжлүүлэх үү? Баталгаажуулахын тулд "USTGAH" гэж бичнэ үү: ')
            if confirmation != 'USTGAH':
                self.stdout.write(self.style.ERROR('Цуцлагдсан.'))
                return

        with transaction.atomic():
            deleted_count, deleted_details = spam_users.delete()

        self.stdout.write(self.style.SUCCESS(f'\n✓ Амжилттай устгалаа! Нийт хэрэглэгч: {user_count}'))
        if deleted_details:
            self.stdout.write('\nУстгасан объектуудын дэлгэрэнгүй:')
            for model, count in deleted_details.items():
                if count > 0:
                    self.stdout.write(f'  {model}: {count}')
