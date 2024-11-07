from django.db import models
from django.contrib.auth.models import User, Group
from accounts.models import Author, Province, Zone, Grade, Level
from datetime import datetime, timezone, timedelta
from ckeditor.fields import RichTextField

# Create your models here.

class Olympiad(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(default='')
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    final_message = models.TextField(default='''Бодлогууд таалагдсан гэдэгт итгэлтэй байна. Цаашид улам хичээн суралцаарай!''')
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)
    is_open = models.BooleanField(default=True)
    is_grading = models.BooleanField(default=False)
    rounds = [
        (0, 'Бусад олимпиад'),
        (1, 'Сонгон шалгаруулалт'),
        (2, 'Дүүргийн олимпиад'),
        (3, 'Хотын олимпиад'),
        (4, 'Улсын олимпиад'),
        (5, 'Олон улсын олимпиад'),
        (6, 'Олон улсын бусад'),
    ]
    round = models.IntegerField(choices=rounds, default=0)
    next_round = models.ForeignKey('Olympiad', related_name='next', on_delete=models.SET_NULL, null=True, blank=True)
    types = [
        (0, 'Уламжлалт'),
        (1, 'Тест'),
    ]
    type = models.IntegerField(choices=types, default=0)
    school_year = models.ForeignKey('SchoolYear', on_delete=models.SET_NULL, null=True, blank=True)
    month = models.IntegerField(null=True, blank=True)
    num = models.IntegerField(default=1)
    level = models.ForeignKey(Level, on_delete=models.SET_NULL, null=True, blank=True)
    host = models.ForeignKey(Province, on_delete=models.SET_NULL, null=True, blank=True)
    json_results = models.TextField(null=True, blank=True)
    def __str__(self):
        return '{}'.format(self.name)

    def get_problem_ids(self):
        problems = self.problem_set.all().order_by('order')
        ids = []
        for problem in problems:
            ids.append(problem.id)
        return ids

    def get_school_year(self):
        return self.school_year.name

    def get_level(self):
        return self.level.name

    def get_round(self):
        return self.rounds[self.round][1]

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

    class Meta:
        ordering = ['-school_year_id','-id']


class SchoolYear(models.Model):
    name = models.CharField(max_length=10, null=True, blank=True)
    start = models.DateField(null=True, blank=True)
    end = models.DateField(null=True, blank=True)
    descr = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        ordering = ['-name']

    def __str__(self):
        return '{} хичээлийн жил'.format(self.name)


class Round(models.Model):
    name = models.CharField(max_length=100)
    descr = models.TextField(null=True, blank=True)
    is_official = models.BooleanField(default=True)

    def __str__(self):
        return '{}'.format(self.name)


class Topic(models.Model):
    class Category(models.TextChoices):
        ALG = 'ALG', 'Алгебр'
        COM = 'COM', 'Комбинаторик'
        GEO = 'GEO', 'Геометр'
        NUM = 'NUM', 'Тооны онол'
        MIX = 'MIX', 'Хольмог'

    category = models.CharField(
        max_length=3,
        choices=Category.choices,
        default=Category.ALG,
    )
    name = models.CharField(max_length=120)

    def __str__(self):
        return '{}'.format(self.name)


class Problem(models.Model):
    author = models.ForeignKey(Author, on_delete=models.SET_NULL, null=True, blank=True)
    olympiad = models.ForeignKey(Olympiad, on_delete=models.SET_NULL, null=True, blank=True)
    order = models.IntegerField(default=1)
    statement = models.TextField(null=True, blank=True)
    max_score = models.IntegerField(default=7)

    class States(models.IntegerChoices):
        proposed = 0, 'Дэвшигдсэн'
        selected = 1, 'Сонгогдсон'

    state = models.IntegerField(
        choices=States.choices,
        default=States.proposed
    )

    class ProblemTypes(models.IntegerChoices):
        tranditional = 0, 'Уламжлалт'
        selection = 1, 'Сонгох'
        fill = 2, 'Нөхөх'

    type = models.IntegerField(
        choices=ProblemTypes.choices,
        default=ProblemTypes.tranditional
    )

    numerical_answer = models.BigIntegerField(null=True, blank=True)
    comments = models.TextField(null=True, blank=True)
    topics = models.ManyToManyField("Topic", blank=True)

    class Meta:
        permissions = [
            ("edit_problem", "Can edit problem"),
        ]

    def get_results(self):
        return self.result_set.filter().order_by('score')

    def get_nongraded(self):
        return self.result_set.filter(state=1).count()

    def get_graded(self):
        return self.result_set.filter(state=2).count()

    def get_disputed(self):
        return self.result_set.filter(state=3).count()

    def is_active(self):
        if self.get_nongraded() + self.get_disputed() > 0:
            return True
        else:
            return False

    def __str__(self):
        return '{}, {}, {}-р бодлого'.format(self.olympiad.name, self.olympiad.school_year.name, self.order)


class AnswerChoice(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    order = models.IntegerField()
    label = models.CharField(max_length=8)
    value = models.TextField(null=False, default='')
    points = models.IntegerField()

    def __str__(self):
        return 'Бодлого №{}, Сонголт {} = {}'.format(self.problem.id, self.label, self.value)


class Solution(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.SET_NULL, null=True, blank=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    content = models.TextField(null=True, blank=False)

    class Meta:
        permissions = [
            ("edit_solution", "Can edit solution"),
        ]

    def __str__(self):
        return 'Бодлого №{}-ийн бодолт'.format(self.problem.id)


class Result(models.Model):
    contestant = models.ForeignKey(User, related_name='contest_results', on_delete=models.CASCADE, null=True, blank=True)
    user_grade = models.IntegerField(default=0)
    olympiad = models.ForeignKey(Olympiad, on_delete=models.SET_NULL, null=True, blank=True)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    answer = models.BigIntegerField(null=True, blank=True)
    coordinator = models.ForeignKey(User, related_name='coordinated_results', on_delete=models.SET_NULL, null=True, blank=True)
    confirmed_by = models.ForeignKey(User, related_name='confirmed_results', on_delete=models.SET_NULL, null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    grader_comment = models.TextField(default='', blank=True)
    source_file = models.TextField(default='', blank=True)

    class States(models.IntegerChoices):
        not_submitted = 0, 'Хариулаагүй'
        submitted = 1, 'Засагдаагүй'
        graded = 2, 'Урьдчилсан'
        disputed = 3, 'Маргаантай'
        approved = 4, 'Зөвшөөрөгдсөн'
        finalized = 5, 'Батлагдсан'

    state = models.IntegerField(
        choices=States.choices,
        default=States.not_submitted
    )

    date = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return '{}, {}, Бодлого {}, {} оноо'.format(self.contestant.first_name, self.olympiad.name, self.problem.order, self.score)

    def get_upload_num(self):
        return self.upload_set.filter(is_official=True).count()

    def get_uploads(self):
        return self.upload_set.filter(is_official=True)

    def get_supplements_num(self):
        return self.upload_set.filter(is_official=False).count()

    def get_supplements(self):
        return self.upload_set.filter(is_official=False)

    def get_score(self):
        if self.score:
            return float(self.score)
        elif self.score == 0:
            return 0
        return ''

    def get_state(self):
        if self.state == 0:
            return 'Хариулаагүй'
        elif self.state == 1:
            return 'Засагдаагүй'
        elif self.state == 2:
            return 'Урьдчилсан'
        elif self.state == 3:
            return 'Маргаантай'
        elif self.state == 4:
            return 'Зөвшөөрөгдсөн'
        else:
            return 'Батлагдсан'

    class Meta:
        permissions = [
            ("edit_result", "Дүн оруулах"),
            ("confirm_result", "Дүн баталгаажуулах")
        ]


class Upload(models.Model):
    result = models.ForeignKey(Result, on_delete=models.CASCADE)
    upload_time = models.DateTimeField(auto_created=True,auto_now_add=True)
    is_official = models.BooleanField(default=True)
    def file_to(instance, filename):
        return 'static/results/' + str(filename)
    file = models.ImageField(upload_to=file_to)

    def __str__(self):
        return 'Бодлого №{}'.format(self.result.problem.id)


class Comment(models.Model):
    result = models.ForeignKey(Result, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.TextField(blank=False)
    recommendation = models.FloatField(null=True, blank=True)


class Threshold(models.Model):
    olympiad = models.ForeignKey(Olympiad, related_name='thresholds', on_delete=models.CASCADE)
    province = models.ForeignKey(Province, on_delete=models.SET_NULL, null=True, blank=True)
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True)
    min_score = models.IntegerField(default=7)



class Award(models.Model):
    olympiad = models.ForeignKey(Olympiad, related_name='awards', on_delete=models.CASCADE, null=True, blank=True)
    contestant = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    grade = models.ForeignKey(Grade, related_name='awards', on_delete=models.SET_NULL, null=True, blank=True)

    class Place(models.TextChoices):
        GOLD = 'Алт', 'Алтан медаль'
        SILVER = 'Мөнгө', 'Мөнгөн медаль'
        BRONZE = 'Хүрэл', 'Хүрэл медаль'
        SPECIAL = 'Тусгай', 'Тусгай шагнал'
        OUTSTANDING = 'Уран бодолт', 'Уран бодолт'
        FIRST = 'I шат', 'I шат'
        SECOND = 'II шат', 'II шат'

    place = models.CharField(
        max_length=128,
        choices=Place.choices,
        default=Place.GOLD,
    )
    # хуучин шагналуудыг баталгаажуулах
    confirmed_by = models.ForeignKey(User, related_name='confirmed_awards', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        permissions = [
            ('edit_award', 'Шагнал засах'),
            ('confirm_award', 'Шагнал баталгаажуулах')
        ]


class Team(models.Model):
    schoolYear = models.ForeignKey(SchoolYear, on_delete=models.SET_NULL, null=True, blank=True)
    province = models.ForeignKey(Province, related_name='teams', on_delete=models.SET_NULL, null=True, blank=True)
    zone = models.ForeignKey(Zone, related_name='teams', on_delete=models.SET_NULL, null=True, blank=True)
    ranking = models.IntegerField(default=0)

    def getDescription(self):
        if self.zone.id == 5:
            return '"Багануур, Багахангай, Налайх" дүүргийн баг'
        else:
            return '"' + self.province.name + '"-ийн баг'

    def __str__(self):
        return '{}, {} он'.format(self.getDescription(), self.schoolYear.name)

class TeamMember(models.Model):
    user = models.ForeignKey(User, related_name='teams', on_delete=models.SET_NULL, null=True, blank=True)
    team = models.ForeignKey(Team, related_name='members', on_delete=models.SET_NULL, null=True, blank=True)
    olympiad = models.ForeignKey(Olympiad, on_delete=models.SET_NULL, null=True, blank=True)
    ranking = models.IntegerField(default=0)

    def __str__(self):
        return '{} баг, {}'.format(self.team.getDescription(),self.user.first_name)


class Article(models.Model):
    oldid = models.IntegerField()
    title = models.CharField(max_length=500,null=True, blank=True)
    intro = models.TextField(null=True, blank=True)
    descr = RichTextField(null=True, blank=True)
    year = models.ForeignKey('SchoolYear', on_delete=models.SET_NULL, null=True, blank=True)
    startdate = models.DateField(null=True, blank=True)
    enddate = models.DateField(null=True, blank=True)
    imagesource = models.CharField(max_length=200,null=True, blank=True)
    author = models.ForeignKey(Author, on_delete=models.SET_NULL, null=True, blank=True)
    isspec = models.BooleanField(default=False)
    embedcode = models.TextField(null=True, blank=True)
    pictures = models.TextField(null=True, blank=True)
    files = models.TextField(null=True, blank=True)
    tags = models.TextField(null=True, blank=True)
    sawcount = models.IntegerField(null=True, blank=True)
    isshow = models.BooleanField(default=True)
    createuserid = models.IntegerField(null=True, blank=True)
    createdate = models.DateField(null=True, blank=True)
    updatedate = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-year_id','-isspec']

    def __str__(self):
        return '{}'.format(self.title)

class Tag(models.Model):
    name = models.CharField(max_length=128)
    def __str__(self):
        return '{}'.format(self.name)

class OlympiadGroup(models.Model):
    name = models.CharField(max_length=128)
    olympiads = models.ManyToManyField(Olympiad, blank=True)

    def __str__(self):
        return self.name


class ScoreSheet(models.Model):
    user = models.ForeignKey(User, related_name='results', on_delete=models.CASCADE, null=True, blank=True)
    olympiad = models.ForeignKey(Olympiad, on_delete=models.CASCADE)
    s1 = models.IntegerField(default=0)
    s2 = models.IntegerField(default=0)
    s3 = models.IntegerField(default=0)
    s4 = models.IntegerField(default=0)
    s5 = models.IntegerField(default=0)
    s6 = models.IntegerField(default=0)
    s7 = models.IntegerField(default=0)
    s8 = models.IntegerField(default=0)
    s9 = models.IntegerField(default=0)
    s10 = models.IntegerField(default=0)
    s11 = models.IntegerField(default=0)
    s12 = models.IntegerField(default=0)
    s13 = models.IntegerField(default=0)
    s14 = models.IntegerField(default=0)
    s15 = models.IntegerField(default=0)
    s16 = models.IntegerField(default=0)
    s17 = models.IntegerField(default=0)
    s18 = models.IntegerField(default=0)
    s19 = models.IntegerField(default=0)
    s20 = models.IntegerField(default=0)
    total = models.IntegerField(default=0)
    prizes = models.TextField(null=True, blank=True)
    place = models.IntegerField(default=1)
    def __str__(self):
        return "{} олимпиад, {}".format(self.olympiad.name, self.user)

    def length(self):
        return self.olympiad.problem_set.count()

    def save(self, *args, **kwargs):
        # Calculate total before saving
        self.total = sum(
            getattr(self, f's{i}') for i in range(1, 21)
        )
        super().save(*args, **kwargs)

