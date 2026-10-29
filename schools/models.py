from django.db import models
from django.contrib.auth.models import User, Group
from django.db.models import UniqueConstraint


class School(models.Model):
    user = models.ForeignKey(User, related_name='moderating', on_delete=models.SET_NULL, null=True, blank=True)
    manager = models.ForeignKey(User, related_name='managing', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Сургуулийн удирдлага/менежер")
    group = models.OneToOneField(Group, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Хамаарах бүлэг")
    province = models.ForeignKey("accounts.Province", related_name='moderators', on_delete=models.CASCADE)
    name = models.CharField(max_length=200, default='ЕБС')
    alias = models.CharField(
        max_length=1023,
        blank=True,
        null=True,
        help_text="Сургуулийн өөр нэр, товчлол эсвэл нэмэлт хайлтын alias"
    )
    is_sent_confirmation = models.BooleanField(default=False)
    is_received_confirmation = models.BooleanField(default=False)
    is_official_participation = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, verbose_name="Идэвхтэй",
                                    help_text="Татан буугдсан/хаагдсан сургуулийг идэвхгүй болгоно")
    official_levels = models.ManyToManyField(
        "accounts.Level",
        blank=True,
        related_name='official_schools',
        verbose_name="Албан ёсны оролцооны түвшингүүд"
    )

    class Meta:
        # unique_together-ийн оронд constraints ашиглах
        constraints = [
            UniqueConstraint(fields=['user', 'group'], name='unique_user_group_combination')
        ]

    def __str__(self):
        return "{}".format(self.name)

    def user_has_access(self, user):
        """
        Хэрэглэгч энэ сургуулийг удирдах эрхтэй эсэхийг шалгана.
        Staff, moderator, manager, эсвэл аймгийн manager бол эрхтэй.
        """
        if user.is_staff:
            return True
        if self.user == user:
            return True
        if self.manager == user:
            return True

        # Аймгийн удирдах ажилтан/бүртгэгч багш эрх шалгах
        if self.province and self.province.user_has_access(user):
            return True

        return False


class UploadedExcel(models.Model):
    file = models.FileField(upload_to='excel_uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.file.name} ({self.uploaded_at})"


class EnrollmentLog(models.Model):
    """
    Сурагчийн сургуулийн гишүүнчлэлийн өөрчлөлтийн түүх (audit).
    schools.enrollment service-ээр бичигдэнэ.
    """
    class Action(models.TextChoices):
        REQUEST = 'request', 'Сургууль сонгосон (хүсэлт)'
        ENROLL = 'enroll', 'Сургуульд бүртгэсэн'
        TRANSFER = 'transfer', 'Сургууль шилжүүлсэн'
        UNENROLL = 'unenroll', 'Сургуулиас хассан'

    user = models.ForeignKey(User, related_name='enrollment_logs', on_delete=models.CASCADE)
    action = models.CharField(max_length=16, choices=Action.choices)
    from_school = models.ForeignKey(School, related_name='+', on_delete=models.SET_NULL, null=True, blank=True)
    to_school = models.ForeignKey(School, related_name='+', on_delete=models.SET_NULL, null=True, blank=True)
    performed_by = models.ForeignKey(User, related_name='+', on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['to_school', 'action', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user_id} {self.action} {self.from_school_id}→{self.to_school_id}"


class StudentTransfer(models.Model):
    """
    Сурагчийг нэг сургуулиас нөгөөд шилжүүлэх хүсэлт. Илгээгч сургууль
    үүсгэж, хүлээн авагч сургуулийн бүртгэгч багш зөвшөөрснөөр сурагч
    шилжинэ. Шийдвэр гартал сурагч хуучин сургуульдаа үлдэнэ.
    schools.transfers service-ээр удирдагдана.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Хүлээгдэж буй'
        ACCEPTED = 'accepted', 'Хүлээн авсан'
        REJECTED = 'rejected', 'Татгалзсан'
        CANCELLED = 'cancelled', 'Цуцалсан'

    user = models.ForeignKey(User, related_name='school_transfers', on_delete=models.CASCADE)
    from_school = models.ForeignKey(School, related_name='outgoing_transfers', on_delete=models.CASCADE)
    to_school = models.ForeignKey(School, related_name='incoming_transfers', on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    note = models.CharField(max_length=255, blank=True)
    requested_by = models.ForeignKey(User, related_name='+', on_delete=models.SET_NULL, null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(User, related_name='+', on_delete=models.SET_NULL, null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']
        constraints = [
            UniqueConstraint(fields=['user'], condition=models.Q(status='pending'),
                             name='one_pending_transfer_per_user'),
        ]
        indexes = [
            models.Index(fields=['to_school', 'status']),
            models.Index(fields=['from_school', 'status']),
        ]

    def __str__(self):
        return f"{self.user_id} {self.from_school_id}→{self.to_school_id} ({self.status})"
