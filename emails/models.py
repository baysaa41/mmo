# emails/models.py
from django.db import models
from django.contrib.auth.models import User
from ckeditor_uploader.fields import RichTextUploadingField

# --- ШИНЭЧЛЭЛ: Илгээгч хаягийн сонголтуудыг энд тодорхойлно ---
FROM_EMAIL_CHOICES = [
    ('baysa@mmo.mn', 'baysa@mmo.mn'),
    ('baysa@integral.mn', 'baysa@integral.mn'),
    ('baysa@mathminds.club', 'baysa@mathminds.club'),
    ('info@mmo.mn', 'info@mmo.mn'),
    ('registration@mmo.mn', 'registration@mmo.mn'),
]

class EmailCampaign(models.Model):
    name = models.CharField(max_length=200)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    html_message = RichTextUploadingField(null=True, blank=True, verbose_name="HTML мессеж")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    # --- ШИНЭЧЛЭЛ: Илгээгч имэйлийг сонгох талбар нэмэгдсэн ---
    from_email = models.CharField(
        max_length=255,
        choices=FROM_EMAIL_CHOICES,
        default=FROM_EMAIL_CHOICES[0][0],
        verbose_name='Илгээгч имэйл хаяг'
    )

    is_tested = models.BooleanField(default=False, verbose_name='Тест илгээсэн эсэх')
    test_sent_at = models.DateTimeField(null=True, blank=True, verbose_name='Тест илгээсэн огноо')
    test_recipient_email = models.EmailField(blank=True, null=True, verbose_name='Тест имэйл хаяг')

    filter_active_year = models.BooleanField(default=False, verbose_name='Сүүлийн жилд нэвтэрсэн')
    filter_teachers = models.BooleanField(default=False, verbose_name='Багш нар')
    filter_students = models.BooleanField(default=False, verbose_name='Сурагчид')
    filter_school_managers = models.BooleanField(default=False, verbose_name='Сургуулийн менежер')

    specific_province = models.ForeignKey(
        'accounts.Province',
        on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Аймаг'
    )
    specific_school = models.ForeignKey(
        'schools.School',
        on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Сургууль'
    )

    use_custom_list = models.BooleanField(default=False, verbose_name='Custom имэйл жагсаалт')
    unique_per_email = models.BooleanField(
        default=True,
        verbose_name='Нэг имэйл рүү 1 удаа',
        help_text='Үнэн бол нэг имэйл хаяг руу зөвхөн 1 удаа илгээнэ. Худал бол хэрэглэгч бүрт илгээнэ (ижил имэйлтэй хэрэглэгчид бүгдэд явна).'
    )

    STATUS_CHOICES = [
        ('draft', 'Draft'), ('queued', 'Queued'), ('sending', 'Sending'),
        ('sent', 'Sent'), ('failed', 'Failed'), ('paused', 'Paused'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    total_recipients = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    daily_limit = models.IntegerField(default=50000)
    emails_sent_today = models.IntegerField(default=0)
    last_reset_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.name


class EmailRecipient(models.Model):
    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name='recipients')
    email = models.EmailField()
    name = models.CharField(max_length=100, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_test = models.BooleanField(default=False, null=True, blank=True)

    STATUS_CHOICES = [
        ('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed'), ('bounced', 'Bounced'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    message_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        # --- ӨӨРЧЛӨЛТ: unique_together-г user болон campaign-аар сольсон ---
        unique_together = ['campaign', 'user']
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['status', 'sent_at']),
        ]

    def __str__(self):
        user_info = f"User: {self.user_id}" if self.user else "No User"
        return f"{self.email} ({user_info}) - {self.campaign.name}"


class EmailUnsubscribe(models.Model):
    # --- ӨӨРЧЛӨЛТ: Unsubscribe-г хэрэглэгчид тулгуурласан болгосон ---
    email = models.EmailField(db_index=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    unsubscribed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"User ID: {self.user_id} ({self.email}) - Unsubscribed"


class EmailBounce(models.Model):
    BOUNCE_TYPE_CHOICES = [
        ('hard', 'Hard Bounce'), ('soft', 'Soft Bounce'), ('complaint', 'Complaint'),
    ]
    email = models.EmailField(db_index=True)
    bounce_type = models.CharField(max_length=20, choices=BOUNCE_TYPE_CHOICES)
    message_id = models.CharField(max_length=255, blank=True)
    recipient = models.ForeignKey(EmailRecipient, on_delete=models.SET_NULL, null=True, blank=True)
    notification_data = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['email', 'bounce_type'])]

    def __str__(self):
        return f"{self.email} - {self.bounce_type}"