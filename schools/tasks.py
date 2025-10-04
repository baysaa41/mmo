# schools/tasks.py
from celery import shared_task
from .email_service import SchoolEmailService
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_welcome_email_task(user_id, school_name):
    """
    Шинэ хэрэглэгчид тавтай морилно уу имэйл илгээх background task
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user = User.objects.get(id=user_id)

        # Password reset link-тэй имэйл илгээх
        success, error = SchoolEmailService.send_new_user_welcome_with_reset_link(
            user,
            school_name,
            request=None  # Celery task-д request байхгүй
        )

        if success:
            logger.info(f"Welcome email sent to user {user_id}")
            return {'status': 'success', 'user_id': user_id}
        else:
            logger.error(f"Failed to send email to user {user_id}: {error}")
            return {'status': 'failed', 'error': error}

    except Exception as e:
        logger.error(f"Task failed for user {user_id}: {e}", exc_info=True)
        return {'status': 'error', 'exception': str(e)}