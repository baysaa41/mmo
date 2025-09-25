from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from accounts.views.auth import CustomPasswordResetView
import accounts.views as accounts_views


urlpatterns = ([
    path('select2/', include('django_select2.urls')),
    path('schools/', include('schools.urls')),
    path('files/', include('file_management.urls')),
    path('', include('posts.urls')),  # Homepage now points to the posts app
    path('admin/clearcache/', include('clearcache.urls')),
    path('admin/', admin.site.urls),
    path('tinymce/', include('tinymce.urls')),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path('accounts/', include('accounts.urls')),
    path('accounts/', include('django_registration.backends.activation.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('olympiads/', include('olympiad.urls')),
    path('send_email/', accounts_views.email.send_email_with_attachments, name='send_email_with_attachments'),
    path('password_reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
])

if settings.DEBUG:
    # Development үед Django өөрөө static болон media файлыг үйлчилнэ
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    if getattr(settings, "STATICFILES_DIRS", None):
        urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
else:
    # Production үед зөвхөн media-г Django үйлчилнэ
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
