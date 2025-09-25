import re
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from olympiad.models import Olympiad, Problem


class Command(BaseCommand):
    help = "LaTeX файл ашиглан олимпиадууд болон бодлогуудыг импортлох"

    def add_arguments(self, parser):
        parser.add_argument("filename", type=str, help="Олимпиадын LaTeX файл")
        parser.add_argument(
            "--force-delete",
            action="store_true",
            help="Өмнөх бодлогуудыг устгаад шинээр оруулна",
        )

    def handle(self, *args, **options):
        filename = options["filename"]
        force_delete = options["force_delete"]

        try:
            with open(filename, "r", encoding="utf-8") as f:
                tex = f.read()
        except FileNotFoundError:
            raise CommandError(f"Файл олдсонгүй: {filename}")

        # Олимпиадын хэсгүүдийг задлах
        sections = re.split(r'\\section\{ММО-(\d+)\}', tex)

        if len(sections) <= 1:
            self.stdout.write(self.style.WARNING("Ямар ч олимпиад олдсонгүй."))
            return

        for i in range(1, len(sections), 2):
            olympiad_num = int(sections[i])
            olympiad_name = f"ММО-{olympiad_num}"
            content = sections[i + 1]

            # Он тооцоолох: 1-р олимпиад = 1965 он
            year = 1964 + olympiad_num
            start_time = datetime(year, 5, 1)
            end_time = datetime(year, 5, 2)

            # Олимпиад үүсгэх эсвэл авах
            olympiad, created = Olympiad.objects.get_or_create(
                name=olympiad_name,
                school_year_id=olympiad_num,
                defaults={
                    "level_id": 5,   # F (11–12)
                    "round": 4,      # Улсын олимпиад
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"{olympiad_name} олимпиад үүсгэлээ"))
            else:
                # Хуучин олимпиад байвал update хийж хадгалах
                olympiad.start_time = start_time
                olympiad.end_time = end_time
                olympiad.level_id = 5
                olympiad.round = 4
                olympiad.save()

                if force_delete:
                    olympiad.problem_set.all().delete()
                    self.stdout.write(self.style.WARNING(
                        f"{olympiad_name} аль хэдийн байсан → бодлогуудыг устгаад дахин оруулна"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"{olympiad_name} аль хэдийн байсан → бодлогуудыг үлдээв (--force-delete өгсөн тохиолдолд устгана)"
                    ))
                    continue  # бодлого нэмэхгүй

            # Бүх бодлогыг regex-ээр авах
            problems = re.findall(
                r'\\begin\{question\}(?:\[.*?\])?\s*(.*?)\\end\{question\}',
                content,
                re.S
            )

            if problems:
                for order, prob in enumerate(problems, start=1):
                    Problem.objects.create(
                        olympiad=olympiad,
                        order=order,
                        statement=prob.strip(),
                    )
                self.stdout.write(f" → {len(problems)} бодлого нэмэгдлээ")
            else:
                self.stdout.write(f" → Бодлого олдсонгүй, зөвхөн олимпиад үлдлээ")
