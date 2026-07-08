from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import Grade, UserMeta, Province, Zone, TeacherStudent, Author

User = get_user_model()

# Unregister the default User admin if registered
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

# Custom UserAdmin with search_fields for autocomplete
class UserAdmin(BaseUserAdmin):
    search_fields = ['username', 'first_name', 'last_name', 'email']
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff']

admin.site.register(User, UserAdmin)

# Register your models here.

admin.site.register(Grade)


class UserMetaAdmin(admin.ModelAdmin):
    list_select_related = ('user',)
    autocomplete_fields = ['user']

admin.site.register(UserMeta, UserMetaAdmin)


class ZoneAdmin(admin.ModelAdmin):
    autocomplete_fields = ['contact_person']

admin.site.register(Zone, ZoneAdmin)


class TeacherStudentAdmin(admin.ModelAdmin):
    list_select_related = ('teacher', 'student')
    autocomplete_fields = ['teacher', 'student']

admin.site.register(TeacherStudent, TeacherStudentAdmin)


class AuthorAdmin(admin.ModelAdmin):
    autocomplete_fields = ['user']

admin.site.register(Author, AuthorAdmin)

class ProvinceAdmin(admin.ModelAdmin):
    list_display = ('name','zone')
    autocomplete_fields = ['contact_person']

admin.site.register(Province,ProvinceAdmin)