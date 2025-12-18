# accounts/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views

# Import the new view modules
from .views import auth, display, email, ajax, admin
from schools.views import change_student_password_view

urlpatterns = [
    # Display Views
    path('users/', display.users, name='account_users'),
    path('users/<int:group_id>/', display.group_users, name='group_users'),
    path('staff/', display.staff, name='account_staff'),

    # Participant Search & Merge Requests
    path('search/', display.participant_search, name='participant_search'),
    path('merge-request/create/', display.create_merge_request, name='create_merge_request'),
    path('merge-request/<int:pk>/', admin.merge_request_detail, name='merge_request_detail'),
    path('merge-requests/', admin.merge_requests_list, name='merge_requests_list'),
    path('merge-request/<int:pk>/approve/', admin.merge_request_approve, name='merge_request_approve'),
    path('merge-request/<int:pk>/reject/', admin.merge_request_reject, name='merge_request_reject'),
    # User confirmation URLs (no login required)
    path('merge-request/<int:pk>/confirm/<int:user_id>/<str:token>/', display.merge_request_confirm, name='merge_request_user_confirm'),
    path('merge-request/<int:pk>/decline/<int:user_id>/<str:token>/', display.merge_request_reject, name='merge_request_user_decline'),

    # Auth Views
    path('profile/', auth.profile, name='user_profile'),
    path('profile/<int:user_id>/', auth.user_profile_edit, name='user_profile_edit'),
    path('profile/done/', auth.profile_ready, name='user_profile_done'),
    path('password/<int:user_id>/', change_student_password_view, name='user_password'),
    path('login/', auth.login_view, name='user_login'),
    path('logout/', auth.logout_view, name='user_logout'),
    # profile-d surguuli songoh
    path('ajax/load-schools/', ajax.load_schools, name='ajax_load_schools'), # Шинэ URL нэмэх
    path('bulk-add-users/', auth.bulk_add_users_to_school_view, name='bulk_add_users_to_school'),

    # Email Views
    path('createmails/', email.create_mails, name='user_createmails'),
    path('sendmails/', email.send_mass_html_mail, name='user_sendmails'),
    path('track-email/<uuid:token>/', email.track_email_open, name='track_email_open'),
    path('send-to-schools/', email.send_email_to_schools, name='send_email_to_schools'),

    # dashboard
    path('dashboard/', admin.dashboard_view, name='admin_dashboard'),
    path('commands-guide/', admin.command_guide_view, name='commands_guide'),

    path(
        'password-reset/<uidb64>/<token>/',
        auth.CustomPasswordResetConfirmView.as_view(),
        name='password_reset_confirm'
    ),

    path(
        'password-reset-complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),

    path('user-info/', auth.user_info, name='user_info'),
    path('user-profile/', auth.user_full_profile, name='user_full_profile'),
]