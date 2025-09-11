# accounts/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views

# Import the new view modules
from .views import auth, display, email, importers

urlpatterns = [
    # Display Views
    path('users/', display.users, name='account_users'),
    path('users/<int:group_id>/', display.group_users, name='group_users'),
    path('staff/', display.staff, name='account_staff'),

    # Auth Views
    path('profile/', auth.profile, name='user_profile'),
    path('profile/done/', auth.profile_ready, name='user_profile_done'),
    path('password/', auth_views.PasswordChangeView.as_view(template_name='registration/change-password.html'), name='user_password'),
    path('login/', auth.login_view, name='user_login'),
    path('logout/', auth.logout_view, name='user_logout'),

    # Email Views
    path('createmails/', email.create_mails, name='user_createmails'),
    path('sendmails/', email.send_mass_html_mail, name='user_sendmails'),
    path('track-email/<uuid:token>/', email.track_email_open, name='track_email_open'),
    path('send-to-schools/', email.send_email_to_schools, name='send_email_to_schools'),

    # Import Views
    path('addusers/', importers.import_file, name='add_users'),
]