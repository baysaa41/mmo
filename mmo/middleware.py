from django.shortcuts import render
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

MAINTENANCE_FLAG_FILE = settings.BASE_DIR / 'maintenance' / 'ON'


class MaintenanceModeMiddleware:
    """
    Maintenance mode middleware - зөвхөн staff болон school moderator-д хандалт олгоно.
    Бусад хэрэглэгчдэд maintenance page харуулна.

    Асаах/унтраах: BASE_DIR/maintenance/ON файлыг үүсгэх/устгах замаар хийнэ
    (settings.py засварлах, серверийг restart хийх шаардлагагүй).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Maintenance mode асаалттай эсэхийг шалгах
        maintenance_mode = MAINTENANCE_FLAG_FILE.is_file()

        if maintenance_mode:
            # Admin, нэвтрэх хуудас эсвэл static файл руу хандалт бол зөвшөөрнө
            allowed_paths = [
                '/admin/',
                '/static/',
                '/media/',
                '/accounts/login/',
                '/accounts/logout/',
                '/password_reset/',
                '/accounts/password_reset/',
                '/password_reset/done/',
                '/reset/',  # Password reset confirm URL-ууд (/reset/<uidb64>/<token>/)
                '/accounts/password-reset/',  # Alternative password reset URLs
                '/password_change/',  # Password change
                '/accounts/password/',  # User password change
                '/o/',  # OAuth2 endpoints
            ]

            # Debug logging
            logger.info(f"Maintenance mode: checking path {request.path}")

            if any(request.path.startswith(path) for path in allowed_paths):
                logger.info(f"Path {request.path} is allowed")
                return self.get_response(request)

            # Хэрэглэгч нэвтэрсэн эсэхийг шалгах
            if request.user.is_authenticated:
                # Staff хэрэглэгч бол зөвшөөрнө
                if request.user.is_staff or request.user.is_superuser:
                    return self.get_response(request)

                # School moderator эсэхийг шалгах
                # School.user field-ээр тодорхойлогддог
                if hasattr(request.user, 'moderating') and request.user.moderating.exists():
                    return self.get_response(request)

                # School manager эсэхийг шалгах
                # School.manager field-ээр тодорхойлогддог
                if hasattr(request.user, 'managing') and request.user.managing.exists():
                    return self.get_response(request)

            # Бусад бүх тохиолдолд maintenance page харуулах
            return render(request, 'maintenance.html', status=503)

        return self.get_response(request)


LAST_ACTIVITY_INTERVAL = 15 * 60  # секунд


class LastActivityMiddleware:
    """
    Нэвтэрсэн хэрэглэгчийн UserMeta.last_activity-г шинэчилнэ.
    Өгөгдлийн сан руу хэт олон бичихгүйн тулд хэрэглэгч бүрт
    LAST_ACTIVITY_INTERVAL секундэд нэг л удаа бичнэ (cache.add атомар).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and not request.path.startswith(('/static/', '/media/')):
            try:
                from django.core.cache import cache
                if cache.add(f'last_activity:{user.pk}', 1, LAST_ACTIVITY_INTERVAL):
                    from django.utils import timezone
                    from accounts.models import UserMeta
                    UserMeta.objects.filter(user_id=user.pk).update(last_activity=timezone.now())
            except Exception:
                # Идэвх бүртгэх алдаа хүсэлтийг унагах ёсгүй
                logger.exception("last_activity шинэчлэхэд алдаа гарлаа")

        return response
