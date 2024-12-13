from django.urls import path
from . import views, result_views, beltgel2023, data_views

urlpatterns = [
    path('', views.list_upcomming_olympiads, name='olympiad_home'),
    path('jsonview/<int:olympiad_id>/', result_views.json_view, name='jsonview'),
    path('json/<int:olympiad_id>/', result_views.json_results, name='jsonview'),
    path('excel/', views.upload_file, name='upload_file'),
    path('supplements/', views.supplement_home, name='olympiad_supplement_home'),
    path('supplements/admin/', views.supplements_view, name='supplements_view'),
    path('supplements/approve/', views.approve_supplement, name='approve_supplement'),
    path('supplements/remove/', views.remove_supplement, name='remove_supplement'),
    path('supplements/<int:olympiad_id>/', views.student_supplement_view, name='student_supplement_view'),
    path('quiz/<int:quiz_id>/', views.quiz_view, name='olympiad_quiz'),
    path('end/<int:quiz_id>/', views.quiz_end, name='olympiad_quiz_end'),
    path('exam/<int:olympiad_id>/', views.exam_student_view, name='olympiad_exam'),
    path('supplements/<int:olympiad_id>/', views.student_supplement_view, name='olympiad_supplements'),
    path('exam/staff/<int:olympiad_id>/<int:contestant_id>/', views.exam_staff_view, name='olympiad_exam_staff'),
    path('quiz/staff/<int:quiz_id>/<int:contestant_id>/', views.quiz_staff_view2, name='olympiad_quiz_staff'),
    path('viewer/', views.result_viewer, name='olympiad_result_viewer'),
    path('upload/', views.get_result_form, name='olympiad_get_result_form'),
    path('grading/<int:problem_id>/', views.exam_grading_view, name='olympiad_exam_grading'),
    path('grading/<int:problem_id>/<int:zone_id>/', views.zone_exam_grading_view, name='zone_olympiad_exam_grading'),
    path('grading/home/', views.grading_home, name='olympiad_grading_home'),
    path('grade/', views.grade, name='olympiad_grade_result'),
    path('grade/<int:zone_id>/', views.zone_grade, name='zone_olympiad_grade_result'),
    path('student/materials', views.student_exam_materials_view, name='student_exam_materials'),
    path('problem/materials', views.problem_exam_materials_view, name='problem_exam_materials'),
    path('getupload/', views.view_result, name='olympiad_view_result'),
    path('problems/<int:olympiad_id>/', views.problems_view, name='olympiad_problems_view'),
    path('problems/', views.problems_home, name='olympiad_problems_home'),
    # results
    path('update/<int:olympiad_id>/', result_views.update_results, name='update_result_views'),
    path('pandas/<int:olympiad_id>/', result_views.pandasView3, name='olympiad_pandas_results'),
    path('results/', result_views.results_home, name='olympiad_results_home'),
    path('result/<int:olympiad_id>/<int:contestant_id>/', result_views.student_result_view, name='olympiad_student_result'),
    # path('results/<int:olympiad_id>/', result_views.result_view_org, name='olympiad_result_view'),
    # path('results/<int:olympiad_id>/', result_views.pandasView, name='olympiad_result_view'),
    path('results/<int:olympiad_id>/', result_views.scoresheet_view, name='olympiad_result_view'),
    path('answers/<int:olympiad_id>/', result_views.answers_view, name='olympiad_answer_view'),
    path('answers/<int:olympiad_id>/<int:group_id>/', result_views.answers_view2, name='olympiad_group_answer_view'),
    # path('results/new/<int:olympiad_id>/', result_views.newResultView, name='olympiad_result_data_view'),
    # path('results/data/<int:olympiad_id>/', result_views.getJSONResults, name='olympiad_get_json_results'),
    # path('results/imo/62/third/', result_views.olympiad_result_imo62_third, name='olympiad_result_imo63_third'),
    # path('results/imo/63/first/', result_views.olympiad_result_imo63_first, name='olympiad_result_imo63_first'),
    # path('results/imo/63/second/', result_views.olympiad_result_imo63_second, name='olympiad_result_imo63_second'),
    # path('results/imo/63/third/', result_views.olympiad_resul_imo63_third, name='olympiad_result_imo63_third'),
    # path('results/imo/64/', result_views.pandasIMO64, name='olympiad_result_imo64'),
    path('results/g/<int:group_id>/', result_views.olympiad_group_result_view, name='olympiad_group_result_view'),
    path('results/import/', result_views.firstRoundResults, name='olympiad_import_first_round'),
    path('certificate/<int:quiz_id>/<int:contestant_id>/', result_views.createCertificate, name='olympiad_certificate'),
    #path('beltgel2023/', beltgel2023.index, name='beltgel_2023'),
    path('stats/<int:problem_id>/', result_views.problem_stats_view, name='problem_stats'),
    path('quizzes/list/<int:school_id>', views.quiz_list_view, name='quiz_list_view'),
    #path('results/data/<int:olympiad_id>', data_views.olympiad_results_json, name='olympiad_results_json'),
    #path('r/<int:olympiad_id>', data_views.results, name='olympiad_results_data'),
    path('scoresheet/<int:olympiad_id>/', result_views.scoresheet_view, name='scoresheet_view'),
]
