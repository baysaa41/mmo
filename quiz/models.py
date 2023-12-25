from django.db import models
from django.contrib.auth.models import User
from datetime import datetime, timezone, timedelta

# Create your models here.

class QuizStatus(models.Model):
    user = models.ForeignKey(User,on_delete=models.SET_NULL,null=True)
    quiz = models.ForeignKey('Quiz', on_delete=models.CASCADE,null=True)
    current = models.IntegerField(default=1)
    sisi = models.CharField(max_length=12)
    first_name = models.CharField(max_length=20,default='')
    last_name = models.CharField(max_length=20,default='')

    def __str__(self):
        return "{}, {}".format(self.user, self.quiz)

class Quiz(models.Model):
    name = models.CharField(max_length=120)
    start_time = models.DateTimeField(null=True,blank=True,editable=True)
    end_time = models.DateTimeField(null=True,blank=True,editable=True)
    final_message = models.TextField(null=True,blank=True)
    class Types(models.IntegerChoices):
        quiz = 0, 'Тест'
        exam = 1, 'Шалгалт'

    quiz_type = models.IntegerField(
        choices=Types.choices,
        default=Types.quiz,
    )

    def __str__(self):
        return "{}".format(self.name)

    def is_active(self):
        now = datetime.now(timezone.utc)
        if self.start_time < now and self.end_time > now:
            return True
        else:
            return False

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

    def is_closed(self):
        threshold = datetime.now(timezone.utc) + timedelta(seconds=-300)
        if self.end_time < threshold:
            return True
        else:
            return False

    def is_open(self):
        threshold = datetime.now(timezone.utc) + timedelta(seconds=-300)
        if self.end_time < threshold:
            return False
        else:
            return True

    def size(self):
        positions = self.problem_set.values_list('order')
        max = 0
        for p in positions:
            x = p[0]
            if x > max:
                max=x
        return max


class Problem(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.SET_NULL, null=True)
    order = models.IntegerField(default=1)
    statement = models.TextField(null=True)

    def get_score(self):
        answer_choices = self.answerchoice_set.all()
        for answer_choice in answer_choices:
            if answer_choice.points > 0:
                return answer_choice.points
        return 0

    def get_answer(self):
        answer_choices = self.answerchoice_set.all()
        for answer_choice in answer_choices:
            if answer_choice.points > 0:
                return answer_choice.label
        return ''

    def __str__(self):
        return "{}. {}".format(self.order,self.statement)


class AnswerChoice(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    order = models.IntegerField(null=True,blank=True)

    class Labels(models.TextChoices):
        A = 'A', 'А'
        B = 'B', 'B'
        C = 'C', 'C'
        D = 'D', 'D'
        E = 'E', 'E'

    label = models.CharField(
        max_length=1,
        choices=Labels.choices,
        default=Labels.A,
    )

    value = models.TextField(null=False, default='')
    points = models.IntegerField(default=2)

    def __str__(self):
        return '{}, {}, {}, {}'.format(self.problem,self.label,self.value,self.points)


class Result(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, null=True)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, null=True)
    choice = models.ForeignKey(AnswerChoice, on_delete=models.CASCADE, null=True, blank=True)
    pos = models.IntegerField(null=True, blank=True)
    score = models.IntegerField(null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    submitted = models.DateTimeField(auto_now_add=True)


class Upload(models.Model):
    result = models.ForeignKey(Result, on_delete=models.CASCADE, null=True)
    def file_to(instance, filename):
        return 'static/uploads/' + str(filename)
    file = models.ImageField(upload_to=file_to)
    uploaded = models.DateTimeField(auto_created=True, auto_now_add=True)

    def delete(self, *args, **kwargs):
        # Delete the associated file when the model instance is deleted
        storage, path = self.file_field.storage, self.file_field.path
        super(YourModel, self).delete(*args, **kwargs)
        storage.delete(path)
    def __str__(self):
        return '{}, {}, {}'.format(self.result.student.username, self.result.problem.quiz.name, self.result.problem.order)