from django.contrib import admin
from .models import FileUpload, FileAccessLog


@admin.register(FileUpload)
class FileUploadAdmin(admin.ModelAdmin):
    list_display = ['file', 'description_short', 'school_year', 'uploader', 'uploaded_at', 'download_count']
    list_filter = ['school_year', 'uploaded_at', 'uploader']
    search_fields = ['description', 'file']
    readonly_fields = ['uploaded_at', 'download_count']
    ordering = ['-uploaded_at']

    def description_short(self, obj):
        """Тайлбарыг богино харуулах"""
        if len(obj.description) > 50:
            return obj.description[:50] + '...'
        return obj.description
    description_short.short_description = 'Тайлбар'

    def download_count(self, obj):
        """Татагдсан тоо"""
        return obj.access_logs.count()
    download_count.short_description = 'Татагдсан тоо'


@admin.register(FileAccessLog)
class FileAccessLogAdmin(admin.ModelAdmin):
    list_display = ['file', 'user', 'downloaded_at']
    list_filter = ['downloaded_at', 'user']
    search_fields = ['file__file', 'user__username']
    readonly_fields = ['file', 'user', 'downloaded_at']
    ordering = ['-downloaded_at']

    def has_add_permission(self, request):
        # Админ хэсгээс шинээр log нэмэхийг хориглох
        return False