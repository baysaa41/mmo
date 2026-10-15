from django.contrib import admin
from .models import School, StudentTransfer
# Register your models here.

class SchoolAdmin(admin.ModelAdmin):
    fields = ('name','province','group', 'user', 'manager')
    list_display = ('name','province', 'user', 'manager')
    list_select_related = ('province', 'user', 'manager')
    autocomplete_fields = ['user', 'manager']

admin.site.register(School, SchoolAdmin)


@admin.register(StudentTransfer)
class StudentTransferAdmin(admin.ModelAdmin):
    list_display = ('user', 'from_school', 'to_school', 'status', 'requested_by', 'requested_at', 'decided_by', 'decided_at')
    list_filter = ('status',)
    search_fields = ('user__username', 'user__last_name', 'user__first_name', 'from_school__name', 'to_school__name')
    raw_id_fields = ('user', 'from_school', 'to_school', 'requested_by', 'decided_by')
