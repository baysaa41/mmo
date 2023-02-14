from django.contrib import admin
from .models import Grade, UserMeta, School, Province, Zone, TeacherStudent, Author

# Register your models here.

admin.site.register(Grade)
admin.site.register(UserMeta)
admin.site.register(School)
admin.site.register(Zone)
admin.site.register(TeacherStudent)
admin.site.register(Author)

class ProvinceAdmin(admin.ModelAdmin):
    list_display = ('name','zone')

admin.site.register(Province,ProvinceAdmin)