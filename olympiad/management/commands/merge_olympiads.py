from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, models
from olympiad.models import Olympiad, Problem, Result, Award, ScoreSheet

class Command(BaseCommand):
    help = 'Нэг буюу хэд хэдэн олимпиадыг нэг үндсэн олимпиад руу нэгтгэнэ.'

    def add_arguments(self, parser):
        parser.add_argument('--primary-olympiad-id', type=int, required=True, help='Хадгалж үлдэх үндсэн олимпиадын ID')
        parser.add_argument('--duplicate-olympiad-ids', type=int, nargs='+', required=True, help='Нэгтгээд устгах олимпиадуудын ID-нууд')

    @transaction.atomic
    def handle(self, *args, **options):
        primary_id = options['primary_olympiad_id']
        duplicate_ids = options['duplicate_olympiad_ids']

        if primary_id in duplicate_ids:
            raise CommandError('Үндсэн олимпиадын ID давхардсан олимпиадын жагсаалтад байж болохгүй.')

        try:
            primary_olympiad = Olympiad.objects.get(pk=primary_id)
            duplicate_olympiads = Olympiad.objects.filter(pk__in=duplicate_ids)
            if len(duplicate_olympiads) != len(duplicate_ids):
                raise CommandError('Давхардсан ID-тай олимпиадын зарим нь олдсонгүй.')
        except Olympiad.DoesNotExist:
            raise CommandError(f'ID={primary_id} бүхий үндсэн олимпиад олдсонгүй.')

        self.stdout.write(self.style.WARNING(f"АНХААР! Дараах олимпиадуудыг нэгтгэх гэж байна:"))
        self.stdout.write(self.style.SUCCESS(f"  - Үндсэн олимпиад (хадгалагдана): '{primary_olympiad.name}' (ID: {primary_id})"))
        for o in duplicate_olympiads:
            self.stdout.write(self.style.WARNING(f"  - Нэгтгэгдэх олимпиад (устгагдана): '{o.name}' (ID: {o.id})"))

        confirmation = input('Энэ үйлдлийг буцаах боломжгүй. Үргэлжлүүлэх үү? (yes/no): ')
        if confirmation.lower() != 'yes':
            self.stdout.write(self.style.ERROR('Үйлдэл цуцлагдлаа.'))
            return

        for dup_olympiad in duplicate_olympiads:
            self.stdout.write(f"\n--- '{dup_olympiad.name}' (ID: {dup_olympiad.id})-г нэгтгэж байна... ---")

            # --- Бодлогуудыг шилжүүлж, дугаарыг нь шинэчлэх ---
            last_order = primary_olympiad.problem_set.aggregate(max_order=models.Max('order'))['max_order'] or 0
            problems_to_merge = dup_olympiad.problem_set.all().order_by('order')

            for i, problem in enumerate(problems_to_merge):
                problem.olympiad = primary_olympiad
                problem.order = last_order + i + 1
                problem.save()
            self.stdout.write(f"  - {problems_to_merge.count()} бодлогыг шилжүүлж, дахин дугаарлалаа.")

            # --- Бусад холбоотой мэдээллийг шилжүүлэх ---
            Result.objects.filter(olympiad=dup_olympiad).update(olympiad=primary_olympiad)
            Award.objects.filter(olympiad=dup_olympiad).update(olympiad=primary_olympiad)
            ScoreSheet.objects.filter(olympiad=dup_olympiad).update(olympiad=primary_olympiad)
            self.stdout.write(f"  - Дүн, шагнал, онооны хуудасны мэдээллийг шилжүүллээ.")

            # Нэгтгэсэн олимпиадыг устгах
            dup_olympiad.delete()
            self.stdout.write(self.style.SUCCESS(f"  - '{dup_olympiad.name}' олимпиадыг амжилттай устгалаа."))

        self.stdout.write(self.style.SUCCESS('\nБүх үйлдэл амжилттай дууслаа!'))