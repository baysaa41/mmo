from django.contrib import admin
from .models import Post

class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'year', 'startdate', 'isshow', 'isspec')
    list_filter = ('year', 'isshow', 'isspec')
    fields = ('title', 'descr', 'year', 'startdate', 'enddate', 'isshow', 'isspec', 'createdate')
    search_fields = ('title', 'descr')

admin.site.register(Post, PostAdmin)