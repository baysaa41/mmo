from django.db import models
from django.contrib.auth.models import User, Group
from accounts.models import Author, Province, Zone, Grade, Level
from datetime import datetime, timezone, timedelta

# Create your models here.

class Quiz(models.Model):
    name = models.CharField(max_length=120)
    min_grade = models.IntegerField(null=True)
    max_grade = models.IntegerField(null=True)
    start_time = models.DateTimeField(null=True,blank=True,editable=True)
    end_time = models.DateTimeField(null=True,blank=True,editable=True)

    def __str__(self):
        return "{}".format(self.name)

    def is_started(self):
        now = datetime.now(timezone.utc)
        if self.start_time < now:
            return True
        else:
            return False

    def is_finished(self):
        now = datetime.now(timezone.utc)
        if self.end_time < now:
            return True
        else:
            return False

    def is_active(self):
        return (self.is_started() and not self.is_finished())

    def __str__(self):
        return "{}".format(self.name)


class Problem(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.SET_NULL, null=True, blank=True)
    order = models.IntegerField(default=1)
    question = models.TextField(default='')
    choice1 = models.TextField(default='')
    choice2 = models.TextField(default='')
    choice3 = models.TextField(default='')
    choice4 = models.TextField(default='')
    choice5 = models.TextField(default='')
    answer = models.IntegerField(null=True)
    score = models.IntegerField(default=4)

    def __str__(self):
        return "{}, {}-р бодлого".format(self.quiz.name, self.order)

class UserAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    problem = models.ForeignKey(Problem, on_delete=models.SET_NULL, null=True, blank=True)
    answer = models.IntegerField(null=True)
    score = models.IntegerField(default=0)
