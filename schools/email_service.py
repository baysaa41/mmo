import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

logger = logging.getLogger(__name__)


class SchoolEmailService:
    """Handles all school-related email operations"""

    @staticmethod
    def send_password_reset_link(user, request=None):
        """
        Send password reset link instead of plain password
        Returns tuple: (success: bool, error_message: str or None)
        """
        try:
            # Generate token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # Build reset URL
            if request:
                domain = request.get_host()
                protocol = 'https' if request.is_secure() else 'http'
            else:
                domain = settings.SITE_URL.replace('https://', '').replace('http://', '')
                protocol = 'https'

            reset_url = f"{protocol}://{domain}/accounts/password-reset/{uid}/{token}/"

            context = {
                'user': user,
                'reset_url': reset_url,
                'expiry_hours': 24,  # Token хүчинтэй байх хугацаа
            }

            text_content = render_to_string(
                'schools/emails/password_reset_link.txt',
                context
            )

            html_content = render_to_string(
                'schools/emails/password_reset_link.html',
                context
            )

            email = EmailMultiAlternatives(
                subject='ММОХ - Нууц үг сэргээх',
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)

            logger.info(f"Password reset link sent to {user.email} (User ID: {user.id})")
            return True, None

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to send password reset link: {error_msg}", exc_info=True)
            return False, error_msg

    @staticmethod
    def send_new_user_welcome_with_reset_link(user, school_name, request=None):
        """
        Шинэ хэрэглэгчид тавтай морилно уу имэйл + password reset link илгээх
        Returns tuple: (success: bool, error_message: str or None)
        """
        try:
            # Password reset token үүсгэх
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # Reset URL бүтээх
            if request:
                domain = request.get_host()
                protocol = 'https' if request.is_secure() else 'http'
            else:
                domain = getattr(settings, 'SITE_URL', 'localhost:8000').replace('https://', '').replace('http://', '')
                protocol = 'https'

            reset_url = f"{protocol}://{domain}/accounts/password-reset/{uid}/{token}/"
            site_url = f"{protocol}://{domain}"

            context = {
                'user': user,
                'username': user.username,
                'school_name': school_name,
                'reset_url': reset_url,
                'site_url': site_url,
                'expiry_hours': 24,
            }

            text_content = render_to_string(
                'schools/emails/new_user_welcome.txt',
                context
            )

            html_content = render_to_string(
                'schools/emails/new_user_welcome.html',
                context
            )

            email = EmailMultiAlternatives(
                subject='ММОХ - Тавтай морилно уу!',
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)

            logger.info(f"Welcome email with reset link sent to {user.email} (User ID: {user.id})")
            return True, None

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to send welcome email: {error_msg}", exc_info=True)
            return False, error_msg

    @staticmethod
    def send_password_reset_notification(user, new_password):
        """Send notification when password is reset by admin"""
        try:
            context = {
                'user': user,
                'new_password': new_password,
                'login_url': settings.SITE_URL + '/accounts/login/',
            }

            text_content = render_to_string(
                'schools/emails/password_reset_notification.txt',
                context
            )

            html_content = render_to_string(
                'schools/emails/password_reset_notification.html',
                context
            )

            email = EmailMultiAlternatives(
                subject='ММОХ - Нууц үг солигдлоо',
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)

            logger.info(f"Password reset email sent to {user.email} (User ID: {user.id})")
            return True, None

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to send password reset email: {error_msg}", exc_info=True)
            return False, error_msg