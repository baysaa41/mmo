from django.db import models
from django.contrib.auth.models import User, Group
from django.db.models import UniqueConstraint


class School(models.Model):
    user = models.ForeignKey(User, related_name='moderating', on_delete=models.SET_NULL, null=True, blank=True)
    group = models.OneToOneField(Group, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Хамаарах бүлэг")
    province = models.ForeignKey("accounts.Province", related_name='moderators', on_delete=models.CASCADE)
    name = models.CharField(max_length=200, default='ЕБС')
    alias = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="Сургуулийн өөр нэр, товчлол эсвэл нэмэлт хайлтын alias"
    )
    is_sent_confirmation = models.BooleanField(default=False)
    is_received_confirmation = models.BooleanField(default=False)

    class Meta:
        # unique_together-ийн оронд constraints ашиглах
        constraints = [
            UniqueConstraint(fields=['user', 'group'], name='unique_user_group_combination')
        ]

    def __str__(self):
        return "{}".format(self.group.name)


class UploadedExcel(models.Model):
    file = models.FileField(upload_to='excel_uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.file.name} ({self.uploaded_at})"
