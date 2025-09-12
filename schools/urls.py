from django.urls import path
from .views import school_moderators_view, edit_profile, edit_user_in_group, school_dashboard, manage_school_by_level

urlpatterns = [
    path('', school_moderators_view, name='school_moderators_list'),

    # Шинэ URL-ууд
    # жишээ: /schools/32/ -> Удирдах самбар
    path('<int:school_id>/', school_dashboard, name='school_dashboard'),
    # жишээ: /schools/32/level/5/ -> Ангилал удирдах хуудас
    path('<int:school_id>/level/<int:level_id>/', manage_school_by_level, name='manage_school_by_level'),

    # Хуучин URL-ууд
    path('profile/edit/', edit_profile, name='edit_profile'),
    path('profile/edit/<int:user_id>/', edit_user_in_group, name='edit_user_in_group'),
]
