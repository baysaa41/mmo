from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='myquiz_index'),
    path('check/', views.check_quiz, name='myquiz_check_quiz'),
    path('quiz/<int:quiz_id>/', views.start_quiz, name='myquiz_start_quiz'),
    path('save/', views.save_answer, name='myquiz_save_answer'),
    path('clear/', views.clear_all, name='myquiz_clear_all'),
    path('results/<int:quiz_id>/', views.pandasView, name='myquiz_results'),
    ]