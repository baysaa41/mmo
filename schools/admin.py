from django.contrib import admin
from .models import School
# Register your models here.

class SchoolAdmin(admin.ModelAdmin):
    fields = ('name','province','group')
    list_display = ('name','province')

admin.site.register(School, SchoolAdmin)
