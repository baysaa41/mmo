from django.contrib import admin
from .models import School
# Register your models here.

class SchoolAdmin(admin.ModelAdmin):
    fields = ('name','province','group', 'user', 'manager')
    list_display = ('name','province', 'user', 'manager')

admin.site.register(School, SchoolAdmin)
