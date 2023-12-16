from django.urls import path
from . import views, results, beltgel2023

urlpatterns = [
    path('', views.list_upcomming_olympiads, name='olympiad_home'),
    path('excel/', views.upload_file, name='upload_file'),
    path('supplements/', views.supplement_home, name='olympiad_supplement_home'),
    path('supplements/admin/', views.supplements_view, name='supplements_view'),
    path('supplements/approve/', views.approve_supplement, name='approve_supplement'),
    path('supplements/remove/', views.remove_supplement, name='remove_supplement'),
    path('supplements/<int:olympiad_id>/', views.student_supplement_view, name='student_supplement_view'),
    path('mmo57/', views.mmo57, name='mmo57'), # olympiadiin huvaari
    path('quiz/<int:quiz_id>/', views.quiz_view, name='olympiad_quiz'),
    path('end/<int:quiz_id>/', views.quiz_end, name='olympiad_quiz_end'),
    path('exam/<int:olympiad_id>/', views.exam_student_view, name='olympiad_exam'),
    path('supplements/<int:olympiad_id>/', views.student_supplement_view, name='olympiad_supplements'),
    path('exam/staff/<int:olympiad_id>/<int:contestant_id>/', views.exam_staff_view, name='olympiad_exam_staff'),
    path('viewer/', views.result_viewer, name='olympiad_result_viewer'),
    path('upload/', views.get_result_form, name='olympiad_get_result_form'),
    path('grading/<int:problem_id>/', views.exam_grading_view, name='olympiad_exam_grading'),
    path('grading/<int:problem_id>/<int:zone_id>/', views.zone_exam_grading_view, name='zone_olympiad_exam_grading'),
    path('grading/home/', views.grading_home, name='olympiad_grading_home'),
    path('grade/', views.grade, name='olympiad_grade_result'),
    path('grade/<int:zone_id>/', views.zone_grade, name='zone_olympiad_grade_result'),
    path('result/pdf/<int:result_id>/', views.pdf, name='result_pdf'),
    path('student/materials', views.student_exam_materials_view, name='student_exam_materials'),
    path('problem/materials', views.problem_exam_materials_view, name='problem_exam_materials'),
    path('getupload/', views.view_result, name='olympiad_view_result'),
    path('problems/<int:olympiad_id>/', views.problems_view, name='olympiad_problems_view'),
    path('problems/', views.problems_home, name='olympiad_problems_home'),
    # results
    path('update/<int:olympiad_id>/', results.update_results, name='update_results'),
    path('pandas/<int:quiz_id>/', results.pandasView, name='olympiad_pandas_results'),
    path('results/', results.results_home, name='olympiad_results_home'),
    path('result/<int:olympiad_id>/<int:contestant_id>/', results.student_result_view,
         name='olympiad_student_result'),
    path('results/<int:olympiad_id>/', results.result_view, name='olympiad_result_view'),
    path('results/<int:olympiad_id>/', results.pandasView3, name='olympiad_result_view'),
    path('results/new/<int:olympiad_id>/', results.newResultView, name='olympiad_result_data_view'),
    path('results/data/<int:olympiad_id>/', results.getJSONResults, name='olympiad_get_json_results'),
    path('results/egmo/', results.olympiad_result_egmo, name='olympiad_result_egmo'),
    path('results/imo/62/third/', results.olympiad_result_imo62_third, name='olympiad_result_imo63_third'),
    path('results/imo/63/first/', results.olympiad_result_imo63_first, name='olympiad_result_imo63_first'),
    path('results/imo/63/second/', results.olympiad_result_imo63_second, name='olympiad_result_imo63_second'),
    path('results/imo/63/third/', results.olympiad_result_imo63_third, name='olympiad_result_imo63_third'),
    path('results/imo/64/', results.pandasIMO64, name='olympiad_result_imo64'),
    path('results/mmo/58/second/dund2/', results.olympiad_result_mmo58_second_dund2, name='olympiad_result_mmo58_second_dund2'),
    path('results/mmo/58/second/ahlah/', results.olympiad_result_mmo58_second_ahlah, name='olympiad_result_mmo58_second_ahlah'),
    path('results/mmo/58/second/bagsh/', results.olympiad_result_mmo58_second_bagsh, name='olympiad_result_mmo58_second_bagsh'),
    path('results/import/', results.firstRoundResults, name='olympiad_import_first_round'),
    path('certificate/<int:quiz_id>/<int:contestant_id>/', results.createCertificate, name='olympiad_certificate'),
    path('beltgel2023/', beltgel2023.index, name='beltgel_2023'),
    # path('r/<int:olympiad_id>/', results.result_view, name='result_view')
]
