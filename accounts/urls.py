from django.urls import include, path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('users/', views.users, name='account_users'),
    path('users/<int:group_id>/', views.group_users, name='group_users'),
    path('staff/', views.staff, name='account_staff'),
    path('profile/', views.profile, name='user_profile'),
    path('profile/done/', views.profile_ready, name='user_profile_done'),
    path('password/', auth_views.PasswordChangeView.as_view(template_name='registration/change-password.html'),
         name='user_password'),
    path('createmails/',views.create_mails,name='user_createmails'),
    path('sendmails/',views.send_mass_html_mail,name='user_sendmails'),
    path('create/users/',views.create_users,name='create_users'),
    path('login/', views.login_view, name='user_login'),
    path('logout/', views.logout_view, name='user_logout')
]