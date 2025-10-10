# emails/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.core import signing
from django.core.exceptions import SuspiciousOperation
import json
import logging

from .models import EmailCampaign, EmailUnsubscribe, EmailRecipient, EmailBounce
from .forms import EmailCampaignForm
from .tasks import (
    create_recipients_from_filters,
    create_recipients_from_email_list,
    send_campaign_async,
    send_test_email_task
)

logger = logging.getLogger(__name__)


@staff_member_required
def campaign_list(request):
    """Campaign жагсаалт харуулах"""
    campaigns = EmailCampaign.objects.filter(
        created_by=request.user
    ).order_by('-created_at')

    for campaign in campaigns:
        if campaign.total_recipients > 0:
            completed = campaign.sent_count + campaign.failed_count
            campaign.progress_percent = round((completed / campaign.total_recipients * 100), 1)
        else:
            campaign.progress_percent = 0

    return render(request, 'emails/campaign_list.html', {
        'campaigns': campaigns
    })


@staff_member_required
def create_campaign(request):
    """Шинэ campaign үүсгэх"""
    if request.method == 'POST':
        form = EmailCampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.created_by = request.user
            campaign.save()

            if campaign.use_custom_list:
                email_list = form.cleaned_data.get('email_list', '').strip()
                if email_list:
                    create_recipients_from_email_list.delay(campaign.id, email_list)
                    messages.success(request, 'Campaign үүсгэгдлээ! Имэйл жагсаалт боловсруулж байна...')
                else:
                    messages.warning(request, 'Custom сонгосон бол имэйл жагсаалт оруулна уу!')
            else:
                create_recipients_from_filters.delay(campaign.id)
                messages.success(request, 'Campaign үүсгэгдлээ! Хүлээн авагчдын жагсаалт бэлтгэж байна...')

            return redirect('campaign_detail', campaign_id=campaign.id)
    else:
        form = EmailCampaignForm()

    return render(request, 'emails/campaign_form.html', {
        'form': form
    })


def get_schools_by_province(request):
    """AJAX: Аймгаар сургууль шүүх"""
    province_id = request.GET.get('province_id')
    if province_id:
        try:
            from schools.models import School
            schools = School.objects.filter(province_id=province_id).values('id', 'name').order_by('name')
            return JsonResponse({'schools': list(schools)})
        except Exception as e:
            return JsonResponse({'schools': [], 'error': str(e)}, status=400)
    return JsonResponse({'schools': []})


@staff_member_required
def campaign_detail(request, campaign_id):
    """Campaign дэлгэрэнгүй мэдээлэл"""
    campaign = get_object_or_404(EmailCampaign, id=campaign_id, created_by=request.user)
    stats = {
        'total': campaign.total_recipients,
        'pending': campaign.recipients.filter(status='pending', is_test=False).count(),
        'sent': campaign.sent_count,
        'failed': campaign.failed_count,
        'bounced': campaign.recipients.filter(status='bounced').count(),
        'sent_today': campaign.emails_sent_today,
        'remaining_daily': max(0, campaign.daily_limit - campaign.emails_sent_today),
    }
    if campaign.total_recipients > 0:
        completed = campaign.sent_count + campaign.failed_count
        stats['progress_percent'] = round((completed / campaign.total_recipients * 100), 1)
    else:
        stats['progress_percent'] = 0

    filters_applied = []
    if campaign.use_custom_list: filters_applied.append('Custom имэйл жагсаалт')
    else:
        if campaign.filter_active_year: filters_applied.append('Сүүлийн жилд идэвхитэй')
        if campaign.filter_teachers: filters_applied.append('Багш нар')
        if campaign.filter_students: filters_applied.append('Сурагчид')
        if campaign.filter_school_managers: filters_applied.append('Сургуулийн менежер')
        if campaign.specific_province: filters_applied.append(f'Аймаг: {campaign.specific_province.name}')
        if campaign.specific_school: filters_applied.append(f'Сургууль: {campaign.specific_school.name}')
        if not any([campaign.filter_active_year, campaign.filter_teachers, campaign.filter_students, campaign.filter_school_managers, campaign.specific_province, campaign.specific_school]):
            filters_applied.append('Бүх хэрэглэгчид')

    recent_sent = campaign.recipients.filter(status='sent').order_by('-sent_at')[:50]
    failed = campaign.recipients.filter(status='failed').order_by('-id')[:50]

    return render(request, 'emails/campaign_detail.html', {
        'campaign': campaign, 'stats': stats, 'filters_applied': filters_applied,
        'recent_sent': recent_sent, 'failed': failed
    })


@staff_member_required
def send_test_email(request, campaign_id):
    """Campaign-ийн тест имэйл илгээх"""
    campaign = get_object_or_404(EmailCampaign, id=campaign_id, created_by=request.user)
    if request.method == 'POST':
        test_email = request.POST.get('test_email', '').strip()
        if not test_email:
            messages.error(request, 'Тест имэйл хаяг оруулна уу!')
            return redirect('campaign_detail', campaign_id=campaign.id)

        test_user = User.objects.filter(email=test_email).first()
        recipient, _ = EmailRecipient.objects.update_or_create(
            campaign=campaign, email=test_email, is_test=True,
            defaults={'name': 'Test User', 'status': 'pending', 'user': test_user}
        )

        send_test_email_task.delay(campaign.id, recipient.id)

        campaign.test_recipient_email = test_email
        campaign.test_sent_at = timezone.now()
        campaign.save(update_fields=['test_recipient_email', 'test_sent_at'])
        messages.success(request, f'Тест имэйл {test_email} рүү илгээгдэж байна.')
    return redirect('campaign_detail', campaign_id=campaign.id)


@staff_member_required
def mark_campaign_tested(request, campaign_id):
    """Campaign-ийг тест хийгдсэн гэж тэмдэглэх"""
    campaign = get_object_or_404(EmailCampaign, id=campaign_id, created_by=request.user)
    campaign.is_tested = True
    campaign.save(update_fields=['is_tested'])
    messages.success(request, 'Campaign тест хийгдсэн гэж тэмдэглэгдлээ!')
    return redirect('campaign_detail', campaign_id=campaign.id)


@staff_member_required
def send_campaign(request, campaign_id):
    """Campaign илгээх"""
    campaign = get_object_or_404(EmailCampaign, id=campaign_id, created_by=request.user)
    if campaign.status in ['sent', 'sending']:
        messages.warning(request, 'Campaign аль хэдийн илгээгдсэн эсвэл илгээж байна!')
    else:
        send_campaign_async.delay(campaign.id)
        messages.success(request, 'Campaign илгээж эхэллээ!')
    return redirect('campaign_detail', campaign_id=campaign.id)


@staff_member_required
def pause_campaign(request, campaign_id):
    """Campaign түр зогсоох"""
    campaign = get_object_or_404(EmailCampaign, id=campaign_id, created_by=request.user)
    if campaign.status == 'sending':
        campaign.status = 'paused'
        campaign.save()
        messages.success(request, 'Campaign түр зогсоогдлоо')
    return redirect('campaign_detail', campaign_id=campaign.id)


@staff_member_required
def resume_campaign(request, campaign_id):
    """Campaign үргэлжлүүлэх"""
    campaign = get_object_or_404(EmailCampaign, id=campaign_id, created_by=request.user)
    if campaign.status == 'paused':
        send_campaign_async.delay(campaign.id)
        messages.success(request, 'Campaign дахин эхэллээ')
    return redirect('campaign_detail', campaign_id=campaign.id)


@staff_member_required
def campaign_status_api(request, campaign_id):
    """Real-time статус AJAX-аар авах"""
    campaign = get_object_or_404(EmailCampaign, id=campaign_id, created_by=request.user)
    completed = campaign.sent_count + campaign.failed_count
    progress = (completed / campaign.total_recipients * 100) if campaign.total_recipients > 0 else 0
    return JsonResponse({
        'status': campaign.get_status_display(),
        'sent_count': campaign.sent_count,
        'failed_count': campaign.failed_count,
        'pending_count': campaign.recipients.filter(status='pending', is_test=False).count(),
        'progress_percent': round(progress, 1)
    })


def email_unsubscribe(request):
    """Unsubscribe хуудас (хэрэглэгчийн токен дээр үндэслэсэн)"""
    token = request.GET.get('token', '')
    if not token:
        messages.error(request, 'Unsubscribe хийх токен олдсонгүй.')
        return redirect('campaign_list')

    signer = signing.Signer()
    user_to_unsubscribe = None
    email_to_unsubscribe = ''

    try:
        unsigned_value = signer.unsign(token)
        if unsigned_value.isdigit():
            user_to_unsubscribe = User.objects.get(pk=int(unsigned_value))
            email_to_unsubscribe = user_to_unsubscribe.email
        else:
            email_to_unsubscribe = unsigned_value
            user_to_unsubscribe = User.objects.filter(email=email_to_unsubscribe).first()
    except (signing.BadSignature, User.DoesNotExist, SuspiciousOperation):
        messages.error(request, 'Unsubscribe хийх линк буруу эсвэл хугацаа нь дууссан байна.')
        return redirect('campaign_list')

    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        if user_to_unsubscribe:
            EmailUnsubscribe.objects.update_or_create(
                user=user_to_unsubscribe,
                defaults={'reason': reason, 'email': user_to_unsubscribe.email}
            )
            messages.success(request, f'{user_to_unsubscribe.email} хаяг амжилттай unsubscribe хийгдлээ.')
        else:
            messages.warning(request, f'{email_to_unsubscribe} хаягтай хэрэглэгч системд бүртгэлгүй тул unsubscribe хийх боломжгүй.')
        return redirect('unsubscribe_success')

    return render(request, 'emails/unsubscribe.html', {'email': email_to_unsubscribe})


def unsubscribe_success(request):
    """Unsubscribe амжилттай хуудас"""
    return render(request, 'emails/unsubscribe_success.html')


@csrf_exempt
def handle_sns_notification(request):
    """AWS SNS Bounce/Complaint notification хүлээн авах webhook"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        message_type = request.META.get('HTTP_X_AMZ_SNS_MESSAGE_TYPE')

        if message_type == 'SubscriptionConfirmation':
            logger.info(f"SNS Subscription URL: {data.get('SubscribeURL')}")
            return JsonResponse({'status': 'pending_confirmation'})

        elif message_type == 'Notification':
            message = json.loads(data.get('Message', '{}'))
            notification_type = message.get('notificationType')
            if notification_type == 'Bounce':
                handle_bounce(message)
            elif notification_type == 'Complaint':
                handle_complaint(message)
            return JsonResponse({'status': 'success'})

        return JsonResponse({'status': 'ignored'})
    except Exception as e:
        logger.error(f"SNS notification error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


def handle_bounce(message):
    """Bounce notification шийдэх"""
    bounce_info = message.get('bounce', {})
    bounce_type = 'hard' if bounce_info.get('bounceType') == 'Permanent' else 'soft'
    for recipient in bounce_info.get('bouncedRecipients', []):
        email = recipient.get('emailAddress')
        if email:
            EmailBounce.objects.create(
                email=email,
                bounce_type=bounce_type,
                notification_data=message
            )
            EmailRecipient.objects.filter(email=email, status='sent').update(status='bounced')
            logger.info(f"Recorded bounce for {email}: {bounce_type}")


def handle_complaint(message):
    """Complaint notification шийдэх"""
    complaint_info = message.get('complaint', {})
    for recipient in complaint_info.get('complainedRecipients', []):
        email = recipient.get('emailAddress')
        if email:
            EmailBounce.objects.create(email=email, bounce_type='complaint', notification_data=message)
            users = User.objects.filter(email=email)
            for user in users:
                EmailUnsubscribe.objects.get_or_create(user=user, defaults={'email': email, 'reason': 'Spam complaint'})
            EmailRecipient.objects.filter(email=email).update(status='bounced', error_message='Spam complaint')
            logger.warning(f"Recorded complaint for {email} and auto-unsubscribed associated users.")