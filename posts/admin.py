from django.contrib import admin
from .models import Post

class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'year', 'startdate', 'isshow', 'isspec')
    list_filter = ('year', 'isshow', 'isspec')
    search_fields = ('title', 'content')

admin.site.register(Post, PostAdmin)