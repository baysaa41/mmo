from django.urls import path
from .views import (
    school_moderators_view,
    my_managed_schools_view,
    all_schools_registry_view,
    school_dashboard,
    manage_school_by_level,
    edit_profile,
    edit_user_in_group,
    generate_school_answer_sheet,
    import_school_answer_sheet,
    view_school_olympiad_results,
    school_olympiad_view,
    add_student_to_group_view,
    change_student_password_view,
    manage_all_schools_view,
    change_school_admin_view,
    edit_school_admin_view,
    change_school_admin_password_view,
    school_list_view,
    edit_school_info_view,
    manager_change_moderator_view,
    change_school_manager_view,
    change_school_manager_password_view,
    school_official_levels_view,
    merge_school_users,
)

urlpatterns = [
    # New main views
    path('', my_managed_schools_view, name='my_managed_schools'),
    path('registry/', all_schools_registry_view, name='all_schools_registry'),

    # Backwards compatibility
    path('moderators/', school_moderators_view, name='school_moderators_list'),

    # Manager functionality
    path('<int:school_id>/change-moderator/', manager_change_moderator_view, name='manager_change_moderator'),

    # Staff/admin views
    path('manage-all/', manage_all_schools_view, name='manage_all_schools'),
    path('official-levels/', school_official_levels_view, name='school_official_levels'),
    path('manage-all-schools/<int:school_id>/edit/', edit_school_info_view, name='edit_school_info'),
    path('<int:school_id>/change-admin/', change_school_admin_view, name='change_school_admin'),
    path('<int:school_id>/change-manager/', change_school_manager_view, name='change_school_manager'),
    path('edit-admin/<int:user_id>/', edit_school_admin_view, name='edit_school_admin'),
    path('change-admin-password/<int:user_id>/', change_school_admin_password_view, name='change_school_admin_password'),
    path('change-manager-password/<int:user_id>/', change_school_manager_password_view, name='change_school_manager_password'),
    path('list/', school_list_view, name='school_list'), # email хайлтаар сургуулийн багш нарын мэдээлэл гаргана

    # School management
    path('<int:school_id>/', school_dashboard, name='school_dashboard'),
    path('<int:school_id>/all-users/', manage_school_by_level, {'level_id': 100}, name='school_all_users'),
    path('<int:school_id>/level/<int:level_id>/', manage_school_by_level, name='manage_school_by_level'),
    path('<int:school_id>/merge-users/', merge_school_users, name='merge_school_users'),

    # Olympiad management
    path('<int:school_id>/olympiad/<int:olympiad_id>/', school_olympiad_view, name='school_olympiad_view'),
    path('<int:school_id>/olympiad/<int:olympiad_id>/generate-sheet/', generate_school_answer_sheet, name='generate_school_answer_sheet'),
    path('<int:school_id>/olympiad/<int:olympiad_id>/import-sheet/', import_school_answer_sheet, name='import_school_answer_sheet'),
    path('<int:school_id>/olympiad/<int:olympiad_id>/results/', view_school_olympiad_results, name='view_school_olympiad_results'),

    # User profile management
    path('profile/edit/', edit_profile, name='edit_profile'),
    path('profile/edit/<int:user_id>/', edit_user_in_group, name='edit_user_in_group'),
    path('<int:school_id>/add-student-to-group/<int:user_id>/', add_student_to_group_view, name='add_student_to_group'),
    path('change-student-password/<int:user_id>/', change_student_password_view, name='change_student_password'),
]