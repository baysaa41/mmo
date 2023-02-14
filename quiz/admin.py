from django.contrib import admin
from .models import QuizStatus, Quiz, Problem, AnswerChoice, Result

# Register your models here.

admin.site.register(QuizStatus)
admin.site.register(Quiz)
admin.site.register(Problem)
admin.site.register(AnswerChoice)
admin.site.register(Result)