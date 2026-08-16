from django.utils import timezone
from olympiad.models import Olympiad, SchoolYear


def upcoming_olympiads(request):
    base_qs = Olympiad.objects.select_related('level').filter(
        is_open=True, end_time__gte=timezone.now()
    ).exclude(start_time=None).order_by('start_time')

    next_one = base_qs.first()
    if next_one:
        olympiads = base_qs.filter(start_time__date=next_one.start_time.date())
    else:
        olympiads = base_qs.none()

    return {'upcoming_olympiads': olympiads}


def current_school_year(request):
    now = timezone.now().date()
    school_year = SchoolYear.objects.filter(start__lte=now, end__gte=now).first()
    return {'current_school_year': school_year}
