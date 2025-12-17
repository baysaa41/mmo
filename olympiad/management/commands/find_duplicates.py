from django.core.management.base import BaseCommand
from django.db.models import Count
from olympiad.models import ScoreSheet
from accounts.models import User


class Command(BaseCommand):
    help = 'Нэг олимпиадад нэг сургуульд ижил овог, ижил нэртэй сурагчдыг олох'

    def add_arguments(self, parser):
        parser.add_argument('olympiad_id', type=int, help='Олимпиадын ID')

    def handle(self, *args, **options):
        olympiad_id = options['olympiad_id']

        # ScoreSheet-ээс сургууль, овог, нэрээр бүлэглэх
        duplicates = (
            ScoreSheet.objects.filter(olympiad_id=olympiad_id)
            .values(
                'school_id',
                'school__name',
                'school__province__name',
                'user__last_name',
                'user__first_name'
            )
            .annotate(count=Count('id'))
            .filter(count__gt=1)
            .order_by('school__province__name', 'school__name', 'user__last_name', 'user__first_name')
        )

        if not duplicates:
            self.stdout.write(self.style.SUCCESS('Давхардсан сурагч олдсонгүй.'))
            return

        self.stdout.write(f'\nОлимпиад ID: {olympiad_id}')
        self.stdout.write(f'Давхардсан бүлгүүдийн тоо: {len(duplicates)}\n')
        self.stdout.write('=' * 80)

        total_duplicates = 0
        for dup in duplicates:
            school_name = dup['school__name']
            province = dup['school__province__name'] or 'Тодорхойгүй'
            last_name = dup['user__last_name']
            first_name = dup['user__first_name']
            count = dup['count']
            total_duplicates += count

            self.stdout.write(f'\n{province} - {school_name}')
            self.stdout.write(f'  Овог: {last_name}, Нэр: {first_name} ({count} сурагч)')

            # Тухайн бүлгийн сурагчдын дэлгэрэнгүй мэдээлэл
            students = ScoreSheet.objects.filter(
                olympiad_id=olympiad_id,
                school_id=dup['school_id'],
                user__last_name=last_name,
                user__first_name=first_name
            ).select_related('user', 'user__data')

            for s in students:
                user = s.user
                grade = getattr(user.data, 'grade', '-') if hasattr(user, 'data') and user.data else '-'
                self.stdout.write(f'    - ID: {user.id}, Анги: {grade}, Нийт оноо: {s.total}')

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(f'Нийт давхардсан сурагчид: {total_duplicates}')
