from django.shortcuts import render
from .models import Post
from olympiad.models import SchoolYear
from datetime import datetime, timezone

def post_list_view(request):
    """
    Displays a list of posts, serving as the site's homepage.
    This logic was moved from the old `accounts.views.index`.
    """
    now = datetime.now(timezone.utc)

    # Determine the active and selected school years
    active_year = SchoolYear.objects.filter(start__lt=now, end__gt=now).first()
    year_id = request.GET.get('year', active_year.id if active_year else None)
    selected_year = SchoolYear.objects.filter(pk=year_id).first() if year_id else None

    posts = []
    prev_year = None
    next_year = None

    if selected_year:
        posts = Post.objects.filter(
            year=selected_year,
            isshow=True,
            startdate__lt=now
        ).exclude(enddate__lt=now).order_by('-isspec', '-startdate')

        prev_year = SchoolYear.objects.filter(pk=selected_year.id - 1).first()
        next_year = SchoolYear.objects.filter(pk=selected_year.id + 1).first()

    context = {
        'posts': posts,
        'year': selected_year,
        'prev': prev_year,
        'next': next_year,
    }

    return render(request, 'posts/post_list.html', context)