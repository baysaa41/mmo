from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from accounts.placeholders import protected_from_deletion_q

class Command(BaseCommand):
    help = 'Deletes inactive users who have not logged in for a specified number of days and have no results.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='The number of days a user must be inactive to be considered for deletion. Defaults to 365.'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulates the command without actually deleting any users.'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skips the confirmation prompt before deleting users.'
        )

    def handle(self, *args, **options):
        days_inactive = options['days']
        dry_run = options['dry_run']
        confirm = options['confirm']

        cutoff_date = timezone.now() - timedelta(days=days_inactive)

        self.stdout.write(self.style.WARNING(f'Finding users who have not logged in since {cutoff_date.strftime("%Y-%m-%d")}...'))

        # Шалгуур:
        # 1. Staff эсвэл superuser биш байх.
        # 2. Сүүлд нэвтрээгүй удсан байх (last_login is Null эсвэл cutoff_date-ээс өмнө).
        # 3. Ямар ч олимпиадад бүртгүүлж, дүн аваагүй байх.
        inactive_users = User.objects.filter(
            is_staff=False,
            is_superuser=False,
            last_login__lt=cutoff_date
        ).exclude(
            # Placeholder эсвэл олимпиадын дүн (Result), шагнал (Award), оноо хуудас (ScoreSheet)-тай
            # хэрэглэгчийг хэзээ ч устгахгүй (accounts/placeholders.py).
            protected_from_deletion_q()
        )

        user_count = inactive_users.count()

        if user_count == 0:
            self.stdout.write(self.style.SUCCESS('No inactive users to delete.'))
            return

        self.stdout.write(f'Found {user_count} inactive user(s) to delete:')
        for user in inactive_users:
            self.stdout.write(f'- {user.username} (Last login: {user.last_login})')

        if dry_run:
            self.stdout.write(self.style.SUCCESS('\n--dry-run mode: No users were deleted.'))
            return

        if not confirm:
            confirmation = input(f'\nAre you sure you want to delete these {user_count} users? [y/N]: ')
            if confirmation.lower() != 'y':
                self.stdout.write(self.style.ERROR('Deletion cancelled by user.'))
                return

        # Хэрэглэгчдийг устгах
        deleted_count, _ = inactive_users.delete()
        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully deleted {deleted_count} inactive user(s).'))
