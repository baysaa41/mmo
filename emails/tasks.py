# emails/tasks.py
from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q, F
from datetime import timedelta, date
from django.template import Template, Context
from django.urls import reverse
from django.core import signing
import logging
import re

from .models import EmailCampaign, EmailRecipient, EmailUnsubscribe, EmailBounce
from schools.models import School

logger = logging.getLogger(__name__)


def get_users_by_filters(campaign):
    """Campaign-ийн шүүлтүүрээр хэрэглэгчдийг зөв логикоор шүүх"""
    base_query = User.objects.filter(is_active=True, email__isnull=False).exclude(email__exact='')
    user_type_filters = Q()
    has_user_type_filter = False

    if campaign.filter_active_year:
        user_type_filters |= Q(last_login__gte=timezone.now() - timedelta(days=365)); has_user_type_filter = True
    if campaign.filter_teachers:
        user_type_filters |= Q(data__level_id__in=[6, 7]); has_user_type_filter = True
    if campaign.filter_students:
        user_type_filters |= Q(data__level_id__lt=6); has_user_type_filter = True
    if campaign.filter_school_managers:
        manager_ids = School.objects.filter(user__isnull=False).values_list('user_id', flat=True)
        user_type_filters |= Q(id__in=manager_ids); has_user_type_filter = True

    if has_user_type_filter:
        base_query = base_query.filter(user_type_filters)

    if campaign.specific_school:
        if campaign.specific_school.group:
            base_query = base_query.filter(groups=campaign.specific_school.group)
        else:
            logger.warning(f"School {campaign.specific_school.id} has no associated group.")
            return User.objects.none()
    elif campaign.specific_province:
        schools_in_province = School.objects.filter(province=campaign.specific_province)
        valid_group_ids = [s.group_id for s in schools_in_province if s.group_id]
        if valid_group_ids:
            base_query = base_query.filter(groups__id__in=valid_group_ids)
        else:
            logger.warning(f"No schools with groups found in province {campaign.specific_province.id}.")
            return User.objects.none()
    return base_query.distinct()


@shared_task
def create_recipients_from_filters(campaign_id):
    """Campaign-ийн filter-д үндэслэн recipients үүсгэх"""
    campaign = None
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        campaign.status = 'queued'; campaign.save()
        users = get_users_by_filters(campaign)
        total_users = users.count()
        campaign.total_recipients = total_users; campaign.save(update_fields=['total_recipients'])

        if total_users == 0:
            campaign.status = 'draft'; campaign.save()
            return "No users found matching filters"

        batch_size = 2000
        for i in range(0, total_users, batch_size):
            batch_users = users[i:i + batch_size]
            recipients = [
                EmailRecipient(campaign=campaign, email=user.email, name=user.get_full_name() or user.username, user=user)
                for user in batch_users
            ]
            if recipients:
                EmailRecipient.objects.bulk_create(recipients, batch_size=1000, ignore_conflicts=True)
        campaign.status = 'draft'; campaign.save()
    except Exception as e:
        logger.error(f"Error creating recipients for campaign {campaign_id}: {e}")
        if campaign:
            campaign.status = 'failed'; campaign.save()
        raise


@shared_task
def create_recipients_from_email_list(campaign_id, email_list_text):
    """Textarea-с имэйл жагсаалт авч recipients үүсгэх"""
    campaign = None
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        campaign.status = 'queued'; campaign.save()

        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, email_list_text)
        unique_emails = list(set([email.strip().lower() for email in emails]))

        if not unique_emails:
            campaign.status = 'draft'; campaign.total_recipients = 0; campaign.save()
            return "No valid emails found in list"

        recipients = []
        for email in unique_emails:
            user = User.objects.filter(email=email).first()
            name = user.get_full_name() or user.username if user else email.split('@')[0]
            recipients.append(EmailRecipient(campaign=campaign, email=email, name=name, user=user))

        if recipients:
            EmailRecipient.objects.bulk_create(recipients, batch_size=1000, ignore_conflicts=True)

        campaign.total_recipients = len(recipients); campaign.status = 'draft'; campaign.save()
        return f"Created {len(recipients)} recipients from email list"
    except Exception as e:
        logger.error(f"Error creating from email list for campaign {campaign_id}: {e}")
        if campaign:
            campaign.status = 'failed'; campaign.save()
        raise


def check_daily_limit(campaign):
    """Өдрийн лимит шалгах ба reset хийх"""
    today = date.today()
    if campaign.last_reset_date < today:
        campaign.emails_sent_today = 0
        campaign.last_reset_date = today
        campaign.save(update_fields=['emails_sent_today', 'last_reset_date'])
    return campaign.daily_limit - campaign.emails_sent_today


@shared_task
def send_email_batch_ses(campaign_id, recipient_ids):
    """Имэйл багцыг илгээх (хэрэглэгчийн unsubscribe шалгалттай)"""
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        recipients = EmailRecipient.objects.filter(id__in=recipient_ids, status='pending').select_related('user')

        unsubscribed_user_ids = set(EmailUnsubscribe.objects.values_list('user_id', flat=True))
        bounced_emails = set(EmailBounce.objects.filter(bounce_type__in=['hard', 'complaint']).values_list('email', flat=True))

        for recipient in recipients:
            if (recipient.user and recipient.user.id in unsubscribed_user_ids) or (recipient.email in bounced_emails):
                recipient.status = 'failed'; recipient.error_message = 'User unsubscribed or bounced'; recipient.save()
                continue

            try:
                signer = signing.Signer()
                token_value = recipient.user.id if recipient.user else recipient.email
                token = signer.sign(str(token_value))
                unsubscribe_url = f"{settings.SITE_URL}{reverse('email_unsubscribe')}?token={token}"

                context = Context({'name': recipient.name or 'User', 'unsubscribe_url': unsubscribe_url})
                text_template = Template(campaign.message + "\n\n---\nТатгалзах: {{ unsubscribe_url }}")
                personalized_message = text_template.render(context)

                msg = EmailMultiAlternatives(subject=campaign.subject, body=personalized_message, from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient.email])
                if campaign.html_message:
                    html_template = Template(campaign.html_message + '<hr><p style="font-size:12px;color:#666;text-align:center;">Татгалзах: <a href="{{ unsubscribe_url }}">энд дарна уу</a></p>')
                    msg.attach_alternative(html_template.render(context), "text/html")

                #if settings.DEBUG:
                #    msg.to = ['baysa.edu@gmail.com'] # Таны тест хаяг

                msg.send()

                recipient.status = 'sent'; recipient.sent_at = timezone.now()
                if hasattr(msg, 'anymail_status'): recipient.message_id = msg.anymail_status.message_id
                recipient.save()

                EmailCampaign.objects.filter(pk=campaign.id).update(
                    sent_count=F('sent_count') + 1,
                    emails_sent_today=F('emails_sent_today') + 1
                )
            except Exception as e:
                recipient.status = 'failed'; recipient.error_message = str(e)[:500]; recipient.save()
                EmailCampaign.objects.filter(pk=campaign.id).update(failed_count=F('failed_count') + 1)
                logger.error(f"Failed to send to {recipient.email}: {e}")
    except Exception as e:
        logger.error(f"Campaign {campaign_id}: Batch send error: {e}")
        raise


@shared_task
def send_campaign_async(campaign_id):
    """Campaign-ийг rate limit-тэй batch-аар явуулах"""
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        if campaign.status in ['sent', 'sending']: return f"Campaign already {campaign.status}"

        campaign.status = 'sending'; campaign.save()
        remaining = check_daily_limit(campaign)
        if remaining <= 0:
            campaign.status = 'paused'; campaign.save()
            return "Daily limit reached, campaign paused"

        pending_recipients = campaign.recipients.filter(status='pending', is_test=False)
        to_send_count = min(pending_recipients.count(), remaining)
        if to_send_count == 0:
            check_campaign_completion.delay(campaign.id)
            return "No pending recipients to send"

        recipient_ids = list(pending_recipients.values_list('id', flat=True)[:to_send_count])
        batch_size, delay = 60, 5
        batch_count = 0
        for i in range(0, len(recipient_ids), batch_size):
            batch_ids = recipient_ids[i:i + batch_size]
            send_email_batch_ses.apply_async(args=[campaign_id, batch_ids], countdown=batch_count * delay)
            batch_count += 1

        total_time = batch_count * delay + 60
        check_campaign_completion.apply_async(args=[campaign_id], countdown=total_time)
        logger.info(f"Campaign {campaign_id}: Queued {to_send_count} emails in {batch_count} batches.")
    except Exception as e:
        if 'campaign' in locals() and campaign:
            campaign.status = 'failed'; campaign.save()
        logger.error(f"Campaign {campaign_id}: Error queueing campaign: {e}")
        raise


@shared_task
def check_campaign_completion(campaign_id):
    """Campaign бүрэн илгээгдсэн эсэхийг шалгах"""
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        if campaign.status not in ['sending', 'paused']: return

        pending_count = campaign.recipients.filter(status='pending', is_test=False).count()
        if pending_count == 0:
            campaign.status = 'sent'; campaign.sent_at = timezone.now(); campaign.save()
            logger.info(f"Campaign {campaign_id} completed!")
        elif check_daily_limit(campaign) <= 0:
            campaign.status = 'paused'; campaign.save()
            logger.info(f"Campaign {campaign_id}: Paused due to daily limit.")
        else:
            check_campaign_completion.apply_async(args=[campaign_id], countdown=60)
    except Exception as e:
        logger.error(f"Campaign {campaign_id}: Error checking completion: {e}")


@shared_task
def resume_paused_campaigns():
    """Celery Beat-аар өдөр бүр ажиллаж, паузласан campaign-уудыг дахин эхлүүлэх"""
    for campaign in EmailCampaign.objects.filter(status='paused'):
        if check_daily_limit(campaign) > 0:
            logger.info(f"Resuming campaign {campaign.id} ({campaign.name})")
            send_campaign_async.delay(campaign.id)


@shared_task
def send_test_email_task(campaign_id, recipient_id):
    """Тест имэйл илгээх task"""
    try:
        recipient = EmailRecipient.objects.get(id=recipient_id, is_test=True)
        campaign = recipient.campaign

        signer = signing.Signer()
        token = signer.sign(str(recipient.user_id) if recipient.user else recipient.email)
        unsubscribe_url = f"{settings.SITE_URL}{reverse('email_unsubscribe')}?token={token}"

        context = Context({'name': recipient.name or 'Test User', 'unsubscribe_url': unsubscribe_url})
        text_template = Template("[ТЕСТ ИМЭЙЛ]\n\n" + campaign.message + "\n\n---\nТатгалзах: {{ unsubscribe_url }}")
        personalized_message = text_template.render(context)

        msg = EmailMultiAlternatives(
            subject=f"[ТЕСТ] {campaign.subject}",
            body=personalized_message,
            from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient.email]
        )
        if campaign.html_message:
            html_template = Template('''<div style="background:#fff3cd;padding:15px;margin-bottom:20px;"><strong>ТЕСТ ИМЭЙЛ</strong></div>''' + campaign.html_message + '''
            <hr><p><a href="{{ unsubscribe_url }}">Татгалзах</a></p>''')
            msg.attach_alternative(html_template.render(context), "text/html")

        msg.send()

        recipient.status = 'sent'; recipient.sent_at = timezone.now()
        if hasattr(msg, 'anymail_status'): recipient.message_id = msg.anymail_status.message_id
        recipient.save()
    except Exception as e:
        if 'recipient' in locals() and recipient:
            recipient.status = 'failed'; recipient.error_message = str(e)[:500]; recipient.save()
        logger.error(f"Test email error for campaign {campaign_id}: {e}")
        raise