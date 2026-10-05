import os

from django.db import models
from django.contrib.auth.models import User
from olympiad.models import SchoolYear


class FileUpload(models.Model):
    class Kind(models.TextChoices):
        GENERAL = 'general', 'Заавар (сургуулийн ажилтнуудад)'
        TRAINING = 'training', 'Олимпиадын бэлтгэлийн материал'

    file = models.FileField(upload_to='files/', blank=True)
    # Файлын оронд гадны холбоос (Google Drive, YouTube г.м.) байж болно
    link = models.URLField('Холбоос', max_length=1000, blank=True, default='',
                           help_text='Google Drive, YouTube г.м. холбоос. Файл оруулахгүй бол заавал бөглөнө.')
    description = models.TextField(default='', blank=True)
    kind = models.CharField('Төрөл', max_length=20, choices=Kind.choices, default=Kind.GENERAL, db_index=True)
    # Бэлтгэлийн материалын талбарууд (жишээ нь: "EGMO бэлтгэл 2026")
    title = models.CharField('Гарчиг', max_length=200, blank=True, default='')
    teachers = models.CharField(
        'Хичээл заасан багш нар', max_length=500, blank=True, default='',
        help_text='Таслалаар тусгаарлана. Жишээ нь: Б. Батбаясгалан, Т. Хулан',
    )
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
        return self.title or self.file.name or self.link

    @property
    def teacher_list(self):
        return [t.strip() for t in self.teachers.split(',') if t.strip()]

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else ''

    @property
    def is_link(self):
        return bool(self.link) and not self.file

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
        return f"{self.user.username} accessed {self.file} at {self.downloaded_at}"