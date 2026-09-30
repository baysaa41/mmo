from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_file, name='upload_file'),
    path('download/<int:file_id>/', views.download_file, name='download_file'),
    path('edit/<int:file_id>/', views.edit_file, name='edit_file'),
    path('delete/<int:file_id>/', views.delete_file, name='delete_file'),
    path('training/', views.training_materials, name='training_materials'),
    path('training/upload/', views.upload_training_material, name='upload_training_material'),
    path('', views.file_list, name='file_list'),
]
