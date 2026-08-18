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

    # Одоогийн хичээлийн жилд удирдамж пост холбогдоогүй бол (жишээ нь шинэ жил
    # эхлээд удирдамж пост нь бэлэн болоогүй үед) удирдамж посттой хамгийн
    # сүүлийн хичээлийн жилийнхийг ашиглана. Ингэснээр цэсний "Олимпиадын
    # удирдамж" линк код дотор хатуу бичсэн пост рүү бус, өгөгдлөөс тодорхойлогдох
    # постад үргэлж холбогдоно.
    guideline_post = school_year.guideline_post if school_year else None
    if not guideline_post:
        fallback_year = SchoolYear.objects.filter(
            guideline_post__isnull=False
        ).order_by('-start').first()
        guideline_post = fallback_year.guideline_post if fallback_year else None

    return {
        'current_school_year': school_year,
        'olympiad_guideline_post': guideline_post,
    }
