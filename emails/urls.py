# emails/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.campaign_list, name='campaign_list'),
    path('create/', views.create_campaign, name='create_campaign'),
    path('schools-by-province/', views.get_schools_by_province, name='get_schools_by_province'),
    path('<int:campaign_id>/', views.campaign_detail, name='campaign_detail'),
    path('<int:campaign_id>/send/', views.send_campaign, name='send_campaign'),
    path('<int:campaign_id>/pause/', views.pause_campaign, name='pause_campaign'),
    path('<int:campaign_id>/resume/', views.resume_campaign, name='resume_campaign'),
    path('<int:campaign_id>/status/', views.campaign_status_api, name='campaign_status_api'),

    # Unsubscribe
    path('unsubscribe/', views.email_unsubscribe, name='email_unsubscribe'),
    path('unsubscribe/success/', views.unsubscribe_success, name='unsubscribe_success'),

    # AWS SNS Webhook
    path('sns/notification/', views.handle_sns_notification, name='sns_notification'),

    path('<int:campaign_id>/send-test/', views.send_test_email, name='send_test_email'),
    path('<int:campaign_id>/mark-tested/', views.mark_campaign_tested, name='mark_campaign_tested'),
]