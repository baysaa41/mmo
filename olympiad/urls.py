# urls.py
from django.urls import path
from . import (
    views_public,
    views_results,
    views_admin,
    views_contest,
    result_views,
)
from .views_contest_cbv import (
    StudentQuizView,
    StudentExamView,
    StudentSupplementView,
    ContestEndView,
)
from .views_api import SaveAnswerAPIView


urlpatterns = [
    # === I. Нүүр хуудас ба үндсэн үзэгдлүүд ===
    path('', views_public.olympiads_home, name='olympiad_home'),
    path('problems/', views_public.problems_home, name='olympiad_problems_home'),
    path('results/', views_results.results_home, name='olympiad_results_home'),
    path('supplements/', views_contest.supplement_home, name='olympiad_supplement_home'),
    path('grading/home/', views_admin.grading_home, name='olympiad_grading_home'),

    # === II. Оролцогчийн хэсэг (Contestant Views) ===
    path('quiz/<int:olympiad_id>/', StudentQuizView.as_view(), name='student_quiz'),
    path('exam/<int:olympiad_id>/', StudentExamView.as_view(), name='student_exam'),
    path('supplements/<int:olympiad_id>/', StudentSupplementView.as_view(), name='student_supplement_view'),
    path('end/<int:olympiad_id>/', ContestEndView.as_view(), name='contest_end'),
    path('student/materials', views_contest.student_exam_materials_view, name='student_exam_materials'),
    path('api/save-answer/', SaveAnswerAPIView.as_view(), name='api_save_answer'),

    # === III. Дүн ба статистик ===
    path('results/<int:olympiad_id>/', views_results.olympiad_results, name='olympiad_result_view'),
    path('results/<int:olympiad_id>/<int:contestant_id>/', views_results.student_result_view, name='olympiad_student_result'),
    path('results/g/<int:group_id>/', views_results.olympiad_group_result_view, name='olympiad_group_result_view'),
    path('stats/<int:problem_id>/', views_results.problem_stats_view, name='problem_stats'),
    path('stats/olympiad/<int:olympiad_id>/', views_admin.olympiad_problem_stats, name='olympiad_problem_stats'),
    path('stats/<int:olympiad_id>/top/', views_public.olympiad_top_stats, name='olympiad_top_stats'),
    path('answers/<int:olympiad_id>/', views_results.answers_view, name='olympiad_answer_view'),

    # === IV. Бодлого ба агуулга ===
    path('problems/<int:olympiad_id>/', views_public.problems_view, name='olympiad_problems_view'),
    path('problems/topics/', views_public.problem_list_with_topics, name='problem_list_with_topics'),

    # === V. Засалт ба админ (Admin/Grading Views) ===
    path('quiz/staff/<int:olympiad_id>/<int:contestant_id>/', views_admin.quiz_staff_view, name='olympiad_quiz_staff'),
    path('exam/staff/<int:olympiad_id>/<int:contestant_id>/', views_admin.exam_staff_view, name='olympiad_exam_staff'),
    path('grading/<int:problem_id>/', views_admin.exam_grading_view, name='olympiad_exam_grading'),
    path('grade/', views_admin.grade, name='olympiad_grade_result'),
    path('update/<int:olympiad_id>/', views_admin.update_results, name='update_result_views'),
    path('scoresheet/<int:scoresheet_id>/change-school/', views_admin.scoresheet_change_school, name='scoresheet_change_school'),
    path('supplements/staff/', views_admin.staff_supplements_view, name='olympiad_supplements_view'),
    path('supplements/aprrove/', views_admin.approve_supplement, name='approve_supplement'),
    path('supplements/remove/', views_admin.remove_supplement, name='remove_supplement'),
    path('results/view/', views_admin.view_result, name='olympiad_result_viewer'),
    path('results/get/form', views_contest.get_result_form, name='olympiad_get_result_form'),

]
