from django.db import models
from django.contrib.auth.models import User
from olympiad.models import SchoolYear


class FileUpload(models.Model):
    file = models.FileField(upload_to='files/')
    description = models.TextField(default='')
    uploader = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    school_year = models.ForeignKey(
        SchoolYear,
        on_delete=models.SET_NULL,
        related_name='uploaded_files',
        null=True,
        blank=True
    )

    class Meta:
        ordering = ['-uploaded_at']  # Сүүлд оруулсан эхэнд

    def __str__(self):
        return self.file.name

    def save(self, *args, **kwargs):
        # Хэрэв school_year заагаагүй бол одоогийн жилийг автоматаар сонго
        if not self.school_year:
            current_year = SchoolYear.get_current() or SchoolYear.objects.first()
            if current_year:
                self.school_year = current_year
        super().save(*args, **kwargs)


class FileAccessLog(models.Model):
    file = models.ForeignKey(FileUpload, on_delete=models.CASCADE, related_name="access_logs")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-downloaded_at']

    def __str__(self):
        return f"{self.user.username} accessed {self.file.file.name} at {self.downloaded_at}"