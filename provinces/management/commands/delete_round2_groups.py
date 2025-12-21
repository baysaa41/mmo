"""
Round2 бүлгүүдийг устгах management command
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.db import transaction
from olympiad.models import Olympiad


class Command(BaseCommand):
    help = 'Round2 бүх бүлгийг устгана (олимпиадын group-ыг null болгож, бүлгийг устгана)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Устгалгүйгээр зөвхөн юу болохыг харуулна',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Round2 бүлгүүдийг олох
        round2_groups = Group.objects.filter(name__startswith='Round2_')

        self.stdout.write(
            self.style.WARNING(f'\n=== Round2 бүлгүүд ===')
        )
        self.stdout.write(f'Нийт: {round2_groups.count()} бүлэг\n')

        if round2_groups.count() == 0:
            self.stdout.write(self.style.SUCCESS('Round2 бүлэг олдсонгүй.'))
            return

        # Статистик
        total_users = 0
        total_olympiads = 0
        groups_with_users = 0
        groups_with_olympiads = 0

        group_details = []

        for group in round2_groups:
            user_count = group.user_set.count()
            olympiads = Olympiad.objects.filter(group=group)
            olympiad_count = olympiads.count()

            total_users += user_count
            total_olympiads += olympiad_count

            if user_count > 0:
                groups_with_users += 1

            if olympiad_count > 0:
                groups_with_olympiads += 1

            group_details.append({
                'group': group,
                'user_count': user_count,
                'olympiads': olympiads,
                'olympiad_count': olympiad_count
            })

        # Статистик харуулах
        self.stdout.write('\n--- Статистик ---')
        self.stdout.write(f'Нийт бүлэг: {round2_groups.count()}')
        self.stdout.write(f'Хэрэглэгчтэй бүлэг: {groups_with_users}')
        self.stdout.write(f'Олимпиадтай бүлэг: {groups_with_olympiads}')
        self.stdout.write(f'Нийт хэрэглэгч: {total_users}')
        self.stdout.write(f'Нийт олимпиад: {total_olympiads}')

        # Дэлгэрэнгүй жагсаалт (эхний 10 харуулах)
        self.stdout.write('\n--- Эхний 10 бүлэг ---')
        for detail in group_details[:10]:
            group = detail['group']
            user_count = detail['user_count']
            olympiad_count = detail['olympiad_count']
            olympiads = detail['olympiads']

            olympiad_names = ', '.join([o.name for o in olympiads]) if olympiad_count > 0 else 'Олимпиадгүй'

            self.stdout.write(f'\n• {group.name}')
            self.stdout.write(f'  - Хэрэглэгч: {user_count}')
            self.stdout.write(f'  - Олимпиад: {olympiad_names}')

        if round2_groups.count() > 10:
            self.stdout.write(f'\n... ба бусад {round2_groups.count() - 10} бүлэг\n')

        # Dry run бол дуусгах
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n--dry-run горимд ажиллаж байгаа тул бүлгүүд устгагдсангүй.')
            )
            self.stdout.write(
                self.style.WARNING('Бодитоор устгахын тулд --dry-run-гүйгээр ажиллуулна уу.')
            )
            return

        # Баталгаажуулалт
        self.stdout.write(
            self.style.WARNING(
                f'\n⚠️  АНХААР: Та {round2_groups.count()} бүлгийг устгах гэж байна!'
            )
        )
        self.stdout.write(
            self.style.WARNING(
                f'Энэ нь {total_users} хэрэглэгчийг бүлгээс хасах ба {total_olympiads} олимпиадын group-ыг null болгоно.'
            )
        )

        confirm = input('\nҮргэлжлүүлэх үү? (yes/no): ')

        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('\nЦуцлагдлаа.'))
            return

        # Устгах үйл явц
        self.stdout.write(self.style.WARNING('\n=== Устгаж байна... ===\n'))

        deleted_groups = 0
        updated_olympiads = 0

        with transaction.atomic():
            for detail in group_details:
                group = detail['group']
                olympiads = detail['olympiads']

                # 1. Олимпиадын group-ыг null болгох
                for olympiad in olympiads:
                    olympiad.group = None
                    olympiad.save()
                    updated_olympiads += 1
                    self.stdout.write(f'  ✓ Олимпиад "{olympiad.name}"-ын group арилгалаа')

                # 2. Бүлгийг устгах (хэрэглэгчид автоматаар хасагдана)
                group_name = group.name
                user_count = detail['user_count']
                group.delete()
                deleted_groups += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Бүлэг "{group_name}" устгагдлаа ({user_count} хэрэглэгч хасагдлаа)'
                    )
                )

        # Дүгнэлт
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Амжилттай дууслаа!'
            )
        )
        self.stdout.write(f'Устгагдсан бүлэг: {deleted_groups}')
        self.stdout.write(f'Шинэчлэгдсэн олимпиад: {updated_olympiads}')
        self.stdout.write(f'Бүлгээс хасагдсан хэрэглэгч: {total_users}')
