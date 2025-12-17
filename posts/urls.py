from django.urls import path
from .views import (
    post_list_view,
    post_view
)

app_name = 'posts'

urlpatterns = [
    path('', post_list_view, name='home'),
    path('post/', post_view, name='post_view'),
    path('view/', post_view, name='post_detail'),  # Alternative URL pattern
]
