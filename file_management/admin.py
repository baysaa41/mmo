from django.contrib import admin
from django.db.models import Count
from .models import FileUpload, FileAccessLog


@admin.register(FileUpload)
class FileUploadAdmin(admin.ModelAdmin):
    list_display = ['file', 'description_short', 'school_year', 'uploader', 'uploaded_at', 'download_count']
    list_select_related = ['school_year', 'uploader']
    list_filter = ['school_year', 'uploaded_at']
    search_fields = ['description', 'file', 'uploader__username']
    readonly_fields = ['uploaded_at', 'download_count']
    ordering = ['-uploaded_at']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_download_count=Count('access_logs'))

    def description_short(self, obj):
        """Тайлбарыг богино харуулах"""
        if len(obj.description) > 50:
            return obj.description[:50] + '...'
        return obj.description
    description_short.short_description = 'Тайлбар'

    def download_count(self, obj):
        """Татагдсан тоо"""
        return obj._download_count
    download_count.short_description = 'Татагдсан тоо'
    download_count.admin_order_field = '_download_count'


@admin.register(FileAccessLog)
class FileAccessLogAdmin(admin.ModelAdmin):
    list_display = ['file', 'user', 'downloaded_at']
    list_select_related = ['file', 'user']
    list_filter = ['downloaded_at']
    search_fields = ['file__file', 'user__username']
    readonly_fields = ['file', 'user', 'downloaded_at']
    ordering = ['-downloaded_at']

    def has_add_permission(self, request):
        # Админ хэсгээс шинээр log нэмэхийг хориглох
        return False