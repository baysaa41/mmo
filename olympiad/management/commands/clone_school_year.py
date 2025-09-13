from django.core.management.base import BaseCommand
from olympiad.models import Olympiad
from datetime import timedelta
from copy import deepcopy
import re

def increase_all_numbers(text):
    return re.sub(r'\d+', lambda m: str(int(m.group()) + 1), text)

def decrease_test_numbers(text):
    pattern = re.compile(r'((?:сорилго|сорил|шалгаруулалт)\s*№\s*)(\d+)', flags=re.IGNORECASE)
    return pattern.sub(lambda m: m.group(1) + str(int(m.group(2)) - 1), text)

def smart_increment(text):
    if not text:
        return text
    return decrease_test_numbers(increase_all_numbers(text))

class Command(BaseCommand):
    help = "Clone Olympiads and their Problems from one SchoolYear to another, showing details and asking confirmation."

    def add_arguments(self, parser):
        parser.add_argument('old_id', type=int, help='Source SchoolYear ID')
        parser.add_argument('new_id', type=int, help='Target SchoolYear ID')

    def handle(self, *args, **options):
        old_id, new_id = options['old_id'], options['new_id']
        olympiads = Olympiad.objects.filter(school_year_id=old_id).order_by("pk")

        if not olympiads.exists():
            self.stdout.write(self.style.ERROR(f"No Olympiads found for SchoolYear {old_id}"))
            return

        # --- Хуулах олимпиадын мэдээллийг дэлгэцэнд үзүүлэх ---
        self.stdout.write(self.style.NOTICE(
            f"\nThe following {olympiads.count()} Olympiads will be cloned "
            f"from SchoolYear {old_id} to {new_id}:\n"
        ))
        for o in olympiads:
            problem_count = o.problem_set.count()
            self.stdout.write(
                f"  - [{o.id}] {o.name or '(no name)'} | "
                f"Тайлбар: {o.description or '(no description)'} | Бодлогоын тоо: {problem_count}"
            )

        # --- Хэрэглэгчээс баталгаажуулалт авах ---
        confirm = input("\nCreate these Olympiads and their Problems? [y/N]: ").strip().lower()
        if confirm not in ('y', 'yes'):
            self.stdout.write(self.style.WARNING("Operation cancelled."))
            return

        # --- Клоныг эхлүүлэх ---
        for orig in olympiads:
            new_olymp = deepcopy(orig)
            new_olymp.pk = None
            new_olymp.name = smart_increment(new_olymp.name)
            new_olymp.description = smart_increment(new_olymp.description)

            if new_olymp.start_time and new_olymp.end_time:
                new_olymp.start_time += timedelta(days=364)
                new_olymp.end_time   += timedelta(days=364)

            new_olymp.school_year_id = new_id
            new_olymp.group = None
            new_olymp.is_open = True
            new_olymp.is_grading = False
            new_olymp.next_round_id = None
            new_olymp.json_results = None
            new_olymp.save()

            problems_qs = orig.problem_set.order_by("order")
            self.stdout.write(f"   Cloning {problems_qs.count()} problems for [{orig.id}] {orig.name}")

            for p in problems_qs:
                p.pk = None
                p.olympiad = new_olymp
                p.statement = ''
                p.save(force_insert=True)

        self.stdout.write(self.style.SUCCESS(
            f"\nSuccessfully cloned {olympiads.count()} Olympiads and their problems from SchoolYear {old_id} to {new_id}."
        ))
