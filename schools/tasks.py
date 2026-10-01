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

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_moderator_changed_notice_task(self, school_id, old_moderator_id, new_moderator_id, changed_by_id, changed_at):
    """Бүртгэгч багш солигдсон тухай мэдэгдэл (schools.moderator.change_moderator-оос дуудагдана)."""
    from datetime import datetime
    from django.contrib.auth import get_user_model
    from .models import School
    from .moderator import send_moderator_changed_notice

    User = get_user_model()
    users = User.objects.in_bulk([i for i in (old_moderator_id, new_moderator_id, changed_by_id) if i])
    school = School.objects.select_related('province', 'manager', 'user').get(id=school_id)
    try:
        return send_moderator_changed_notice(
            school,
            users.get(old_moderator_id),
            users.get(new_moderator_id),
            users.get(changed_by_id),
            datetime.fromisoformat(changed_at),
        )
    except Exception as exc:
        logger.error(f"Moderator change notice failed for school {school_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_account_email_changed_notice_task(self, account_id, old_email, changed_by_id, organization,
                                           province_id, changed_at):
    """Албан аккаунтын имэйл солигдсон тухай мэдэгдэл (schools.moderator.notify_account_email_changed)."""
    from datetime import datetime
    from django.contrib.auth import get_user_model
    from accounts.models import Province
    from .moderator import send_account_email_changed_notice

    User = get_user_model()
    users = User.objects.in_bulk([i for i in (account_id, changed_by_id) if i])
    province = Province.objects.filter(id=province_id).select_related('contact_person', 'registrar').first()
    try:
        return send_account_email_changed_notice(
            users[account_id], old_email, users.get(changed_by_id), organization, province,
            datetime.fromisoformat(changed_at),
        )
    except Exception as exc:
        logger.error(f"Account email change notice failed for user {account_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)
