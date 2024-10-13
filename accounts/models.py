from django.db import models
from django.contrib.auth.models import User
import os
from django.utils.text import slugify
from django.conf import settings


def user_directory_path(instance, filename):
    # Get file extension
    ext = filename.split('.')[-1]

    # Sanitize filename and create new filename with username
    filename = f'{slugify(instance.user.username)}_{slugify(filename)}.{ext}'

    # Return the path relative to MEDIA_ROOT
    return os.path.join('user_uploads', instance.user.username, filename)


class Author(models.Model):
    user = models.OneToOneField(User, related_name='is_author', on_delete=models.CASCADE, primary_key=True)

    def __str__(self):
        return "{}, {}".format(self.user.first_name,self.user.last_name)


class UserMeta(models.Model):
    user = models.OneToOneField(User, related_name='data', on_delete=models.CASCADE, primary_key=True)
    photo = models.ImageField(upload_to=user_directory_path, blank=True)
    reg_num = models.CharField(max_length=12)
    province = models.ForeignKey("Province", on_delete=models.SET_NULL, null=True, blank=True)
    school = models.CharField(max_length=255, blank=True, null=True)
    grade = models.ForeignKey("Grade", on_delete=models.SET_NULL, null=True, blank=True)
    level = models.ForeignKey("Level", on_delete=models.SET_NULL, null=True, blank=True)

    class Gender(models.TextChoices):
        MALE = 'Эр', 'Эрэгтэй'
        FEMALE = 'Эм', 'Эмэгтэй'

    gender = models.CharField(
        max_length=2,
        choices=Gender.choices,
        default='',
    )
    address1 = models.CharField(max_length=240, null=True, blank=True)
    address2 = models.CharField(max_length=240, null=True, blank=True)
    mobile = models.IntegerField(null=True)
    is_valid = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['school']),
            models.Index(fields=['reg_num']),
            models.Index(fields=['mobile']),
            # Add more indexes as needed
        ]

    def __str__(self):
        return '{}'.format(self.user.username)

class TeacherStudent(models.Model):
    teacher = models.ForeignKey(User, related_name='students', on_delete=models.CASCADE)
    student = models.ForeignKey(User, related_name='teachers', on_delete=models.CASCADE)
    date_started = models.DateField(auto_now=True)
    date_finished = models.DateField(null=True, blank=True)

    def __str__(self):
        return '{} - {}'.format(self.teacher.first_name, self.student.first_name)


class Province(models.Model):
    name = models.CharField(max_length=120, null=True)
    zone = models.ForeignKey('Zone', on_delete=models.SET_NULL, null=True)
    contact_person = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        permissions = [
            ("edit_province", "Аймаг дүүргийн мэдээлэл оруулах")
        ]

    def __str__(self):
        return '{}'.format(self.name)


class Zone(models.Model):
    name = models.CharField(max_length=120, null=True)
    description = models.TextField()

    class Meta:
        permissions = [
            ("edit_province", "Аймаг дүүргийн мэдээлэл оруулах")
        ]

    def __str__(self):
        return '{}'.format(self.name)


class School(models.Model):
    name = models.CharField(max_length=120, null=True)
    province = models.ForeignKey(Province, on_delete=models.SET_NULL, null=True)
    contact = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        permissions = [
            ("edit_school", "Сургуулийн мэдээлэл оруулах")
        ]

    def __str__(self):
        return '{}, {}'.format(self.province.name, self.name)


class Grade(models.Model):
    name = models.CharField(max_length=60)

    def __str__(self):
        return '{}'.format(self.name)


class Level(models.Model):
    name = models.CharField(max_length=60)

    def __str__(self):
        return '{}'.format(self.name)

class UserMails(models.Model):
    subject = models.CharField(max_length=256)
    text = models.TextField()
    text_html = models.TextField(default='')
    from_email = models.EmailField()
    to_email = models.EmailField()
    replyto_email = models.EmailField(default="baysa.edu@gmail.com")
    bcc = models.TextField(blank=True,null=True)
    is_sent = models.BooleanField(default=False)

    def __str__(self):
        return  '{}, {}'.format(self.subject,self.to_email)

