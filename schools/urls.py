from django.urls import path
from .views import user_creation_view, school_moderators_view, manage_school

urlpatterns = [
    path('addusers/', user_creation_view, name='search_add_users_to_group'),
    path('', school_moderators_view, name='school_moderators_list'),
    path('<int:school_id>/', manage_school, name='manage_school'),
]
