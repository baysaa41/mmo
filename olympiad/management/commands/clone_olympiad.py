# management/commands/clone_olympiad.py

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from olympiad.models import Olympiad, Problem, SchoolYear

class Command(BaseCommand):
    help = 'ID-гаар заасан олимпиадыг бүх бодлогын хамт хуулбарлаж, шинэ хичээлийн жилд онооно.'

    def add_arguments(self, parser):
        parser.add_argument('source_olympiad_id', type=int, help='Хуулбарлах эх олимпиадын ID')
        parser.add_argument('new_school_year_id', type=int, help='Шинээр үүсэх олимпиадад оноох хичээлийн жилийн ID')
        parser.add_argument(
            '--new-name',
            type=str,
            help='Шинэ олимпиадын нэр. Хэрэв өгөгдөөгүй бол хуучин нэр дээр "(Хуулбар)" гэж залгана.'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        source_olympiad_id = options['source_olympiad_id']
        new_school_year_id = options['new_school_year_id']
        new_name = options.get('new_name')

        self.stdout.write(self.style.NOTICE(f"ID={source_olympiad_id} олимпиадыг хуулбарлаж байна..."))

        try:
            source_olympiad = Olympiad.objects.get(pk=source_olympiad_id)
            new_school_year = SchoolYear.objects.get(pk=new_school_year_id)
        except Olympiad.DoesNotExist:
            raise CommandError(f"ID={source_olympiad_id} олимпиад олдсонгүй.")
        except SchoolYear.DoesNotExist:
            raise CommandError(f"ID={new_school_year_id} хичээлийн жил олдсонгүй.")

        # --- ЗАСВАР: Бодлогуудыг ямар нэг өөрчлөлт хийхээс ӨМНӨ уншиж авах ---
        # list() ашиглан QuerySet-г санах ойд шууд уншина.
        source_problems = list(source_olympiad.problem_set.all())

        # Олимпиадыг хуулбарлаж, шинэ мэдээллийг оноох
        new_olympiad = source_olympiad
        new_olympiad.pk = None
        new_olympiad.school_year = new_school_year

        if new_name:
            new_olympiad.name = new_name
        else:
            new_olympiad.name = f"{source_olympiad.name} (Хуулбар)"

        new_olympiad.save()

        self.stdout.write(self.style.SUCCESS(f"'{new_olympiad.name}' нэртэй шинэ олимпиад (ID={new_olympiad.id}) үүслээ."))

        # Эх олимпиадын бүх бодлогыг хуулбарлах
        new_problems = []
        for problem in source_problems: # Одоо санах ойд хадгалсан жагсаалтаас уншина
            problem.pk = None
            problem.olympiad = new_olympiad
            new_problems.append(problem)

        if new_problems:
            Problem.objects.bulk_create(new_problems)
            self.stdout.write(self.style.SUCCESS(f"{len(new_problems)} ширхэг бодлогыг амжилттай хуулбарлалаа."))
        else:
            self.stdout.write(self.style.WARNING("Эх олимпиадад хуулбарлах бодлого олдсонгүй."))

        self.stdout.write(self.style.SUCCESS("\n--- Үйлдэл амжилттай дууслаа. ---"))