import os
from celery import Celery

# Django төслийн settings.py файлыг Celery-д зааж өгөх
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mmo.settings')

# Celery application үүсгэх
app = Celery('mmo')

# Тохиргоог Django-ийн settings.py файлаас унших
app.config_from_object('django.conf:settings', namespace='CELERY')

# Бүртгэгдсэн бүх Django аппуудаас tasks.py файлуудыг автоматаар олох
app.autodiscover_tasks()

# Celery Beat schedule
app.conf.beat_schedule = {
    'resume-paused-campaigns': {
        'task': 'emails.tasks.resume_paused_campaigns',
        'schedule': 3600.0,  # Цаг бүр шалгах
    },
}