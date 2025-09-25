from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from olympiad.models import Olympiad, Problem, Result, Award, ScoreSheet

class Command(BaseCommand):
    help = 'Олимпиадыг ID-аар нь олж, түүнтэй холбоотой бүх мэдээллийг (бодлого, дүн, шагнал, онооны хуудас) устгана.'

    def add_arguments(self, parser):
        parser.add_argument('olympiad_id', type=int, help='Устгах олимпиадын ID')

    @transaction.atomic
    def handle(self, *args, **options):
        olympiad_id = options['olympiad_id']

        try:
            olympiad = Olympiad.objects.get(pk=olympiad_id)
        except Olympiad.DoesNotExist:
            raise CommandError(f'ID={olympiad_id} бүхий олимпиад олдсонгүй.')

        # Холбоотой өгөгдлийн тоог гаргах
        problem_count = Problem.objects.filter(olympiad=olympiad).count()
        result_count = Result.objects.filter(olympiad=olympiad).count()
        award_count = Award.objects.filter(olympiad=olympiad).count()
        scoresheet_count = ScoreSheet.objects.filter(olympiad=olympiad).count()

        self.stdout.write(self.style.WARNING('--- АНХААРУУЛГА! ---'))
        self.stdout.write(f"Та '{olympiad.name}' (ID: {olympiad_id}) олимпиадыг устгах гэж байна.")
        self.stdout.write("Энэ үйлдлийг хийснээр дараах холбоотой бүх мэдээлэл мөн адил устгагдана:")
        self.stdout.write(f"- Бодлого: {problem_count} ш")
        self.stdout.write(f"- Дүн: {result_count} ш")
        self.stdout.write(f"- Шагнал: {award_count} ш")
        self.stdout.write(f"- Онооны хуудас: {scoresheet_count} ш")

        # Баталгаажуулалтын асуултыг илүү ойлгомжтой болгох
        confirmation = input(f"Энэ үйлдлийг буцаах боломжгүйг ойлгож байна уу? Устгах бол '{olympiad.name}' гэж бичнэ үү: ")

        if confirmation != olympiad.name:
            self.stdout.write(self.style.ERROR('Нэр таарсангүй. Үйлдэл цуцлагдлаа.'))
            return

        self.stdout.write(self.style.NOTICE(f"'{olympiad.name}' олимпиадыг устгаж байна..."))

        # Олимпиадыг устгах. on_delete=CASCADE тохиргоотой холбоотой бүх зүйл автоматаар устгагдана.
        olympiad.delete()

        self.stdout.write(self.style.SUCCESS('\nҮйлдэл амжилттай дууслаа!'))