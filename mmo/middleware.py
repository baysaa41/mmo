from django.shortcuts import render
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class MaintenanceModeMiddleware:
    """
    Maintenance mode middleware - зөвхөн staff болон school moderator-д хандалт олгоно.
    Бусад хэрэглэгчдэд maintenance page харуулна.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Maintenance mode асаалттай эсэхийг шалгах
        maintenance_mode = getattr(settings, 'MAINTENANCE_MODE', False)

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

            # Бусад бүх тохиолдолд maintenance page харуулах
            return render(request, 'maintenance.html', status=503)

        return self.get_response(request)
