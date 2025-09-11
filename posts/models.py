from django.db import models
from olympiad.models import SchoolYear
from ckeditor.fields import RichTextField
from accounts.models import Author

class Post(models.Model):
    oldid = models.IntegerField(default=1)
    title = models.CharField(max_length=500,null=True, blank=True)
    intro = models.TextField(null=True, blank=True)
    descr = RichTextField(null=True, blank=True)
    year = models.ForeignKey(SchoolYear, on_delete=models.SET_NULL, null=True, blank=True)
    startdate = models.DateField(null=True, blank=True)
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
    createdate = models.DateField(null=True, blank=True)
    updatedate = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-year_id','-isspec']

    def __str__(self):
        return '{}'.format(self.title)
