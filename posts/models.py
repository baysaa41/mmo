from django.db import models
from django.contrib.auth.models import User
from olympiad.models import SchoolYear
from ckeditor_uploader.fields import RichTextUploadingField
from accounts.models import Author
from django.utils import timezone
from datetime import date # date-г ашиглахын тулд нэмнэ

# 'year' талбарын default утгыг олох туслах функц
def get_current_school_year():
    """Одоогийн идэвхтэй хичээлийн жилийг буцаана."""
    # timezone.now()-г ашигласнаар таны TIME_ZONE тохиргоонд зөв ажиллана
    today = timezone.now().date()
    # Одоогийн огноог агуулсан хичээлийн жилийг хайх
    school_year = SchoolYear.objects.filter(start__lte=today, end__gte=today).first()
    return school_year

class Post(models.Model):
    oldid = models.IntegerField(default=1)
    title = models.CharField(max_length=500,null=True, blank=True)
    intro = models.TextField(null=True, blank=True)
    descr = RichTextUploadingField(null=True, blank=True)

    # --- ӨӨРЧЛӨЛТ ---
    # default-д дээрх функцийг зааж өгсөн
    year = models.ForeignKey(SchoolYear, on_delete=models.SET_NULL, null=True, blank=True, default=get_current_school_year)

    # --- ӨӨРЧЛӨЛТ ---
    # default-д өнөөдрийн огноог зааж өгсөн
    startdate = models.DateField(null=True, blank=True, default=date.today)

    enddate = models.DateField(null=True, blank=True)
    imagesource = models.CharField(max_length=200,null=True, blank=True)
    author = models.ForeignKey(Author, on_delete=models.SET_NULL, null=True, blank=True)
    isspec = models.BooleanField(default=True)
    embedcode = models.TextField(null=True, blank=True)
    pictures = models.TextField(null=True, blank=True)
    files = models.TextField(null=True, blank=True)
    tags = models.TextField(null=True, blank=True)
    sawcount = models.IntegerField(null=True, blank=True)
    isshow = models.BooleanField(default=True)
    createuserid = models.IntegerField(null=True, blank=True)

    # --- ӨӨРЧЛӨЛТ ---
    # Анх үүсгэх үед огноог автоматаар нэмнэ
    createdate = models.DateField(auto_now_add=True, null=True, blank=True)

    # --- ӨӨРЧЛӨЛТ ---
    # Засвар хийх бүрт огноог автоматаар шинэчилнэ
    updatedate = models.DateField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ['-year_id','-isspec']

    def __str__(self):
        return '{}'.format(self.title)