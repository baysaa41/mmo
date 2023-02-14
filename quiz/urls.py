from django.urls import path
from . import views, editor

urlpatterns = [
    path('', views.indexView, name='quiz_index'),
    path('problems/<int:quiz_id>/', views.problemsView, name='quiz_problems'),
    path('pandas/<int:quiz_id>/', views.pandasView, name='quiz_pandas'),
    path('quizzes/', views.quizzesView, name='quiz_quizzes'),
    path('results/<int:quiz_id>/', views.resultsView, name='quiz_results'),
    path('result/<int:quiz_id>/<int:student_id>/', views.studentResultView, name='quiz_student_result'),
    path('import/', views.importStudents, name='quiz_import'),
    path('exam/<int:quiz_id>/', views.exam_view, name='quiz_exam'),
    path('exam/grading/<int:quiz_id>/', views.exam_grading_view, name='quiz_exam_grading'),
    path('main/<int:quiz_id>/<int:pos>/', views.quizView, name='quiz_main'),
    path('clone/<int:problem_id>/', views.cloneProblem, name='clone_problem'),
    path('end/<int:quiz_id>/', views.quizEnd, name='quiz_end'),
    path('get/', views.get, name='quiz_get_result_form'),
    path('grading/', views.grade, name='exam_results_grade'),
    path('logout/', views.logoutView, name='quiz_logout'),
    path('edit/problem/', editor.edit_problem, name='quiz_edit_problem')
]