from django.db import models
from django.contrib.auth.models import User


class FileUpload(models.Model):
    file = models.FileField(upload_to='files/')
    description = models.TextField(default='')
    uploader = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name


class FileAccessLog(models.Model):
    file = models.ForeignKey(FileUpload, on_delete=models.CASCADE, related_name="access_logs")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} accessed {self.file.file.name} at {self.downloaded_at}"
