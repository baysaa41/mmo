# urls.py (Засварласан хувилбар)

from django.urls import path
from . import views, result_views

urlpatterns = [
    # === 1. Үндсэн ба Нүүр хуудасны Замууд ===
    # Нүүр хуудас: Удахгүй болох олимпиадуудын жагсаалт
    path('', views.list_upcomming_olympiads, name='olympiad_home'),
    # Нэмэлт материалын нүүр хуудас
    path('supplements/', views.supplement_home, name='olympiad_supplement_home'),
    # Бодлогын сангийн нүүр хуудас
    path('problems/', views.problems_home, name='olympiad_problems_home'),
    # Дүнгийн нүүр хуудас
    path('results/', result_views.results_home, name='olympiad_results_home'),
    # Засалтын ажлын нүүр хуудас
    path('grading/home/', views.grading_home, name='olympiad_grading_home'),

    # === 2. Олимпиадад Оролцох (Оролцогчийн Үзэгдэл) ===
    # Тестэн олимпиадад оролцох хуудас
    path('quiz/<int:quiz_id>/', views.quiz_view, name='olympiad_quiz'),
    # Уламжлалт олимпиадад оролцох, бодолт хуулах хуудас
    path('exam/<int:olympiad_id>/', views.exam_student_view, name='olympiad_exam'),
    # Олимпиадын хугацаа дууссаныг мэдэгдэх хуудас
    path('end/<int:quiz_id>/', views.quiz_end, name='olympiad_quiz_end'),
    # Сурагчийн илгээсэн бүх материалыг харах
    path('student/materials', views.student_exam_materials_view, name='student_exam_materials'),

    # === 3. Дүн ба Үзүүлэлт Харах ===
    # Олимпиадын нэгдсэн дүнг хүснэгтээр харах (pandas ашигласан)
    path('results/<int:olympiad_id>/', views.olympiad_scores, name='olympiad_result_view'),
    # Тодорхой оролцогчийн хувийн дүнг дэлгэрэнгүй харах
    path('result/<int:olympiad_id>/<int:contestant_id>/', result_views.student_result_view, name='olympiad_student_result'),
    # Оролцогчдын өгсөн хариултуудын жагсаалт (админд зориулсан)
    path('answers/<int:olympiad_id>/', result_views.answers_view, name='olympiad_answer_view'),
    # Нэгдсэн олимпиадын бүлгийн дүнг харах
    path('results/g/<int:group_id>/', result_views.olympiad_group_result_view, name='olympiad_group_result_view'),
    # Тухайн олимпиадын бодлогуудыг харах
    path('problems/<int:olympiad_id>/', views.problems_view, name='olympiad_problems_view'),
    # Бодлогын статистик мэдээллийг харах
    path('stats/<int:problem_id>/', result_views.problem_stats_view, name='problem_stats'),

    # === 4. Засалт ба Удирдлага (Багш/Админы Үзэгдэл) ===
    # Excel файлаас олимпиадын дүнг бөөнөөр импортлох
    path('excel/', views.upload_file, name='upload_file'),
    # Багш/ажилтан сурагчийн тестийн хариултыг оруулах/засах
    path('quiz/staff/<int:quiz_id>/<int:contestant_id>/', views.quiz_staff_view, name='olympiad_quiz_staff'),
    # Багш/ажилтан сурагчийн нэрийн өмнөөс бодолт хуулах
    path('exam/staff/<int:olympiad_id>/<int:contestant_id>/', views.exam_staff_view, name='olympiad_exam_staff'),
    # Тухайн бодлогын ирүүлсэн бүх бодолтыг засах хуудас
    path('grading/<int:problem_id>/', views.exam_grading_view, name='olympiad_exam_grading'),
    # Нэг бодолтыг үнэлэх (оноо өгөх)
    path('grade/', views.grade, name='olympiad_grade_result'),
    # Тестэн олимпиадын дүнг автоматаар шинэчлэх үйлдэл
    path('update/<int:olympiad_id>/', result_views.update_results, name='update_result_views'),
    # Нэгдүгээр шатны дүнг импортлох
    path('results/import/', result_views.firstRoundResults, name='olympiad_import_first_round'),

    # === 5. Нэмэлт Материалтай Холбоотой Замууд ===
    # Сурагч нэмэлт материал илгээх
    path('supplements/<int:olympiad_id>/', views.student_supplement_view, name='student_supplement_view'),
    # Админ нэмэлт материалуудыг хянах
    path('supplements/admin/', views.supplements_view, name='supplements_view'),
    # Нэмэлт материалыг баталгаажуулах
    path('supplements/approve/', views.approve_supplement, name='approve_supplement'),
    # Нэмэлт материалыг устгах
    path('supplements/remove/', views.remove_supplement, name='remove_supplement'),


    # === 6. Бусад ба Туслах Замууд (AJAX, PDF, г.м.) ===
    # AJAX: Оролцогчийн илгээсэн бодолтыг харуулах
    path('viewer/', views.result_viewer, name='olympiad_result_viewer'),
    # AJAX: Файл хуулах формыг авах
    path('upload/', views.get_result_form, name='olympiad_get_result_form'),
    # Хуулсан зургийг харуулах
    path('getupload/', views.view_result, name='olympiad_view_result'),
    # PDF гэрчилгээ үүсгэх
    path('certificate/<int:quiz_id>/<int:contestant_id>/', result_views.createCertificate, name='olympiad_certificate'),
    # problem/materials зам одоогоор ашиглагдаагүй
    path('problem/materials', views.problem_exam_materials_view, name='problem_exam_materials'),
]