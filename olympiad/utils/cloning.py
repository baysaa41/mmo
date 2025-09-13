from .models import Olympiad, Result, ScoreSheet

def clone_olympiad(olympiad_id):
    try:
        original_olympiad = Olympiad.objects.get(pk=olympiad_id)

        # Clone the author (excluding the primary key)
        new_olympiad = Olympiad.objects.get(pk=olympiad_id)
        new_olympiad.pk = None
        new_olympiad.save()  # Now, new_author has a new id

        # Clone related books
        problems = original_olympiad.problem_set.all()
        for problem in problems:
            problem.pk = None  # Remove the primary key
            problem.olympiad = new_olympiad  # Assign the new author
            problem.save()  # Save as a new book
        return new_olympiad
    except Olympiad.DoesNotExist:
        print('Olympiad not found')
        return None

def clone_school_year(old_id, new_id):
    olympiads = Olympiad.objects.filter(school_year_id=old_id).order_by("pk")
    for olympiad in olympiads:
        olympiad_id = olympiad.id
        original_olympiad = Olympiad.objects.get(pk=olympiad_id)

        # Clone the author (excluding the primary key)
        new_olympiad = Olympiad.objects.get(pk=olympiad_id)
        new_olympiad.pk = None
        new_olympiad.name = new_olympiad.name.replace('ММО-61','ММО-62')
        new_olympiad.name = new_olympiad.name.replace('MMO-61','ММО-62')
        new_olympiad.name = new_olympiad.name.replace('MMO 61','ММО-62')
        new_olympiad.name = new_olympiad.name.replace('ММО 61','ММО-62')
        new_olympiad.name = new_olympiad.name.replace('IMO-66','IMO-67')
        if new_olympiad.start_time.year == 2024:
            new_olympiad.start_time = new_olympiad.start_time.replace(year = 2025)
            new_olympiad.end_time =  new_olympiad.end_time.replace(year = 2025)
        else:
            new_olympiad.start_time = new_olympiad.start_time.replace(year = 2026)
            new_olympiad.end_time = new_olympiad.end_time.replace(year = 2026)
        new_olympiad.description = new_olympiad.description.replace('ММО-61','ММО-62')
        new_olympiad.description = new_olympiad.description.replace('MMO-61','ММО-62')
        new_olympiad.school_year_id = new_id
        new_olympiad.save()  # Now, new_author has a new id

        # Clone related problems
        problems = original_olympiad.problem_set.all().order_by("order")
        for problem in problems:
            problem.pk = None  # Remove the primary key
            problem.statement = ''
            problem.olympiad = new_olympiad  # Assign the new author
            problem.save()  # Save as a new book
