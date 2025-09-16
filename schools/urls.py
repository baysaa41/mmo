from django.urls import path
from .views import (
    school_moderators_view,
    school_dashboard,
    manage_school_by_level,
    edit_profile,
    edit_user_in_group,
    generate_school_answer_sheet,
    import_school_answer_sheet,
    view_school_olympiad_results,
    school_level_olympiad_view,
    add_student_to_group_view,
    change_student_password_view,
)

urlpatterns = [
    path('', school_moderators_view, name='school_moderators_list'),
    path('<int:school_id>/', school_dashboard, name='school_dashboard'),
    path('<int:school_id>/level/<int:level_id>/', manage_school_by_level, name='manage_school_by_level'),

    path('<int:school_id>/level/<int:level_id>/olympiad/<int:olympiad_id>/', school_level_olympiad_view, name='school_level_olympiad_view'),

    path('<int:school_id>/olympiad/<int:olympiad_id>/generate-sheet/', generate_school_answer_sheet, name='generate_school_answer_sheet'),
    path('<int:school_id>/olympiad/<int:olympiad_id>/import-sheet/', import_school_answer_sheet, name='import_school_answer_sheet'),
    path('<int:school_id>/olympiad/<int:olympiad_id>/results/', view_school_olympiad_results, name='view_school_olympiad_results'),

    path('profile/edit/', edit_profile, name='edit_profile'),
    path('profile/edit/<int:user_id>/', edit_user_in_group, name='edit_user_in_group'),
    path('<int:school_id>/add-student-to-group/<int:user_id>/', add_student_to_group_view, name='add_student_to_group'),
    path('change-student-password/<int:user_id>/', change_student_password_view, name='change_student_password'),
]