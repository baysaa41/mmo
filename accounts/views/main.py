from django.shortcuts import render, redirect
from olympiad.models import SchoolYear
from posts.models import Post
from accounts.models import UserMeta
from datetime import datetime, timezone

def index(request):
    # Хэрэв хэрэглэгч нэвтэрсэн бол профайлаа гүйцэт бөглөсөн эсэхийг шалгана
    if request.user.is_authenticated:
        meta, created = UserMeta.objects.get_or_create(user=request.user)
        if not meta.is_valid:
            return redirect('user_profile')

    now = datetime.now(timezone.utc)

    # Одоо идэвхтэй байгаа хичээлийн жилийг олно
    active_year = SchoolYear.objects.filter(start__lt=now, end__gt=now).first()

    # Хэрэглэгч өөр жил сонгосон эсэхийг URL-аас шалгана
    year_id = request.GET.get('year', active_year.id if active_year else None)
    year = SchoolYear.objects.filter(pk=year_id).first() if year_id else None

    articles = []
    prev_year = None
    next_year = None

    if year:
        articles = Post.objects.filter(
            year=year,
            isshow=True,
            startdate__lt=now
        ).exclude(enddate__lt=now).order_by('-isspec', '-startdate')

        prev_year = SchoolYear.objects.filter(pk=year.id - 1).first()
        next_year = SchoolYear.objects.filter(pk=year.id + 1).first()

    context = {
        'articles': articles,
        'year': year,
        'prev': prev_year,
        'next': next_year,
    }

    return render(request, 'accounts/site_home.html', context=context)