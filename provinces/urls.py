from django.urls import path
from . import views

urlpatterns = [
    path('', views.my_managed_provinces, name='my_managed_provinces'),
    path('<int:province_id>/', views.province_dashboard, name='province_dashboard'),
    path('<int:province_id>/olympiad/<int:olympiad_id>/',
         views.province_olympiad_view, name='province_olympiad_view'),
    path('<int:province_id>/olympiad/<int:olympiad_id>/add-by-threshold/',
         views.add_students_by_threshold, name='add_students_by_threshold'),
    path('<int:province_id>/olympiad/<int:olympiad_id>/select-top-students/',
         views.select_top_students_by_school, name='select_top_students_by_school'),
    path('<int:province_id>/olympiad/<int:olympiad_id>/add-by-id/',
         views.add_students_by_id, name='add_students_by_id'),
    path('<int:province_id>/olympiad/<int:olympiad_id>/generate-sheet/',
         views.generate_province_answer_sheet, name='generate_province_answer_sheet'),
    path('<int:province_id>/olympiad/<int:olympiad_id>/import-sheet/',
         views.import_province_answer_sheet, name='import_province_answer_sheet'),
    path('<int:province_id>/olympiad/<int:olympiad_id>/results/',
         views.view_province_olympiad_results, name='view_province_olympiad_results'),
    path('<int:province_id>/olympiad/<int:olympiad_id>/round1-results/',
         views.view_round1_province_results, name='view_round1_province_results'),
    path('<int:province_id>/olympiad/<int:olympiad_id>/participants/',
         views.view_province_participants, name='view_province_participants'),
]
