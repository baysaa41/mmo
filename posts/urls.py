from django.urls import path
from .views import post_list_view
from posts.views import post_view

app_name = 'posts'

urlpatterns = [
    path('', post_list_view, name='home'),
    path('post/', post_view, name='post_view'),
]
