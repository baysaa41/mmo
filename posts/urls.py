import datetime

from django.urls import path
from django.views.generic import TemplateView
from .views import (
    post_list_view,
    post_view,
    post_search_view
)

app_name = 'posts'

urlpatterns = [
    path('', post_list_view, name='home'),
    path('post/', post_view, name='post_view'),
    path('view/', post_view, name='post_detail'),  # Alternative URL pattern
    path('search/', post_search_view, name='post_search'),
]

# Статик мэдээллийн хуудсууд (namespace-гүй нэрээр footer-оос холбогдоно)
POLICY_UPDATED = datetime.date(2026, 9, 30)
static_pages = [
    path('about/', TemplateView.as_view(template_name='pages/about.html'), name='about'),
    path('terms/', TemplateView.as_view(template_name='pages/terms.html',
                                        extra_context={'updated': POLICY_UPDATED}), name='terms'),
    path('privacy/', TemplateView.as_view(template_name='pages/privacy.html',
                                          extra_context={'updated': POLICY_UPDATED}), name='privacy'),
]
