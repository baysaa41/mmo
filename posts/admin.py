# posts/admin.py

from django.contrib import admin
from .models import Post

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    # Админы жагсаалтад харагдах хэсэг
    list_display = ('title', 'year', 'author', 'startdate', 'isshow', 'isspec')
    list_filter = ('year', 'isshow', 'isspec', 'author')
    search_fields = ('title', 'descr')

    # Шинээр нэмэх, засах хуудсыг цэгцтэй бүлгүүдэд хуваах
    fieldsets = (
        ('Үндсэн агуулга', {
            'fields': ('title', 'descr', 'author')
        }),
        ('Тохиргоо ба Огноо', {
            'fields': ('year', 'startdate', 'enddate', 'isshow', 'isspec')
        }),
        ('Нэмэлт медиа ба файлууд', {
            'classes': ('collapse',),  # Энэ хэсгийг нууж, дарахад дэлгэгддэг болгоно
            'fields': ('intro', 'imagesource', 'embedcode', 'pictures', 'files', 'tags')
        }),
        ('Системийн мэдээлэл (зөвхөн харах)', {
            'fields': ('createdate', 'updatedate', 'sawcount', 'createuserid', 'oldid')
        }),
    )

    # Автоматаар үүсдэг эсвэл өөрчлөх шаардлагагүй талбарууд
    readonly_fields = ('createdate', 'updatedate', 'sawcount')