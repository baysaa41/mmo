"""Сайтын түвшний error handler-ууд (mmo/urls.py, settings.py-д бүртгэгдэнэ)."""

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.middleware.csrf import REASON_NO_CSRF_COOKIE, REASON_NO_REFERER
from django.template import loader
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


def csrf_failure(request, reason=''):
    """
    CSRF шалгалт унасан үед харагдах хуудас (settings.CSRF_FAILURE_VIEW).

    Django-гийн стандарт django.views.csrf.csrf_failure нь 403_csrf.html
    ФАЙЛ БАЙГАА үед `t.render(request=request)` гэж дуудаж, no_cookie /
    no_referer / reason / DEBUG контекстийг огт дамжуулдаггүй (тэр dict-ийг
    зөвхөн файл байхгүй үед, builtin fallback-д нь л ашигладаг). Иймд
    шалтгаан тус бүрд тохирсон зөвлөгөө харуулахын тулд контекстийг
    өөрсдөө дамжуулж байна.

    Яагаад чухал вэ: бодит хэрэглэгчдийн дийлэнх нь Facebook/Instagram-ийн
    доторх хөтчөөс (in-app browser) нэвтэрдэг бөгөөд тэр үед CSRF cookie
    огт тавигддаггүй (REASON_NO_CSRF_COOKIE). Тэр тохиолдолд «хуудсаа
    дахин ачаал» гэсэн ерөнхий зөвлөгөө тусалдаггүй — хөтчөө солих
    шаардлагатайг хэлэх ёстой.
    """
    context = {
        'reason': reason,
        'no_cookie': reason == REASON_NO_CSRF_COOKIE,
        'no_referer': reason == REASON_NO_REFERER,
        'DEBUG': settings.DEBUG,
    }
    body = loader.get_template('403_csrf.html').render(context, request)
    return HttpResponseForbidden(body)
