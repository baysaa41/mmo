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
        Staff, moderator, эсвэл manager бол эрхтэй.
        """
        if user.is_staff:
            return True
        if self.user == user:
            return True
        if self.manager == user:
            return True
        return False


class UploadedExcel(models.Model):
    file = models.FileField(upload_to='excel_uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.file.name} ({self.uploaded_at})"
