"""Сайтын түвшний error handler-ууд (mmo/urls.py-д бүртгэгдэнэ)."""

from django.http import HttpResponse
from django.template.loader import render_to_string
from django_ratelimit.exceptions import Ratelimited


def handler403(request, exception):
    """
    PermissionDenied → 403 хуудас.

    django_ratelimit хэт олон оролдлогыг PermissionDenied (Ratelimited)
    болгож шиддэг тул Django-гийн default handler нь тайлбаргүй, хоосон
    "403 Forbidden" хуудсыг л буцаадаг байсан — хэрэглэгч (жишээ нь
    бүртгүүлж байгаа багш) яагаад хаагдсанаа ойлгох аргагүй байв.
    Энд тэр хоёрыг ялгаж, тус тусдаа ойлгомжтой монгол хуудас үзүүлнэ.

    Зориуд request=None-оор render хийнэ: context processor-ууд
    (upcoming_olympiads, current_school_year) DB-д ханздаг тул DB унасан
    үед алдааны хуудас өөрөө 500 болж хувирахаас сэргийлж байна.
    """
    template = (
        '403_ratelimited.html' if isinstance(exception, Ratelimited) else '403.html'
    )
    return HttpResponse(
        render_to_string(template),
        status=403,
        content_type='text/html; charset=utf-8',
    )
