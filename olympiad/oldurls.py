from django.urls import path
from . import views, old

urlpatterns = [
    # results
    path('results/igo/<int:level_id>', old.igo_results, name='olympiad_results_igo'),
    path('results/first/', old.results_first_round, name='olympiad_results_first'),
    path('results/second/', old.results_second_round, name='olympiad_results_second'),
    path('results/second/all/', old.results_second_round_all, name='olympiad_results_second_all'),
    path('contestants/second/', old.second_round_contestans, name='olympiad_contestants_second'),
    path('contestants/third/', old.third_round_contestans, name='olympiad_contestants_third'),
    path('twodaysjunior/', old.two_days_junior, name='two_days_junior'),
    path('twodayssenior/', old.two_days_senior, name='two_days_senior'),
    path('imo/', old.imo_results, name='imo_results'),
    path('mmo57/dund', old.mmo57_dund_results, name='mmo57_dund_results'),
    path('mmo57/ahlah', old.mmo57_ahlah_results, name='mmo57_ahlah_results')
]
