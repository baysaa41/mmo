from django.shortcuts import render, redirect, reverse
from django.http.response import HttpResponse, JsonResponse
from .forms import ResultsForm, UploadForm, QuizStatusForm
from django.contrib.auth.models import User
from django.contrib.auth import login, logout
from .auth_backend import PasswordlessAuthBackend
from .models import Problem, Quiz, AnswerChoice, Result, Upload
from datetime import datetime, timezone, timedelta
from django.db import connection
from django.contrib import messages
import pandas as pd
from django.contrib.auth.decorators import login_required
from django.forms import modelformset_factory
from PIL import Image
from accounts.models import UserMeta
import os

ResultsFormSet = modelformset_factory(Result,form=ResultsForm,extra=3)


# Create your views here.

def indexView(request):
    return redirect('quiz_quizzes')
    if request.user.is_authenticated:
        return redirect('quiz_quizzes')
    else:
        if request.method == 'POST':
            try:
                user = User.objects.get(username__iexact=request.POST['sisi'])
                PasswordlessAuthBackend.authenticate(request, user)
                login(request, user, 'django.contrib.auth.backends.ModelBackend')
                return redirect('quiz_quizzes')

            except User.DoesNotExist:
                return render(request, 'error.html',
                              {'error': '{}: дугаартай оюутан бүргэгдээгүй байна.'.format(request.POST['sisi'])})
        form = QuizStatusForm()
        return render(request, 'quiz/login.html', {'form': form})


def logoutView(request):
    logout(request)
    return render(request, 'quiz/logout.html')


@login_required
def quizzesView(request):
    now = datetime.now(timezone.utc)
    quizzes = Quiz.objects.exclude(start_time__gt=now).exclude(end_time__lte=now)

    return render(request, 'quiz/quizzes.html', {'quizzes': quizzes})


@login_required
def quizView(request, quiz_id, pos):
    quiz = Quiz.objects.filter(id=quiz_id).first()

    if not quiz.is_started() and not request.user.is_superuser:
        messages.info(request,'Шалгалт эхлээгүй байна.')
        return redirect('quiz_quizzes')

    if quiz.is_closed() and not request.user.is_superuser:
        messages.info(request,'Шалгалтын хугацаа дууссан байна.')
        return redirect('quiz_quizzes')

    if request.method == 'POST' and 'user_choice' in request.POST.keys() and (quiz.is_open() or request.user.is_superuser):
        user_choice = AnswerChoice.objects.get(pk=int(request.POST['user_choice']))
        result = Result.objects.get(student=request.user, quiz_id=quiz_id, pos=pos)
        result.choice = user_choice
        result.save()
        pos = pos + 1
        if pos > quiz.size():
            return redirect('quiz_end', quiz_id=quiz_id)
        return redirect('quiz_main', quiz_id=quiz_id, pos=pos)

    if quiz.is_finished() and not request.user.is_superuser:
        messages.info(request,'Тестийн хугацаа дууссан.')
        return redirect('quiz_end', quiz_id=quiz_id)

    if quiz.is_active() or request.user.is_superuser:
        if not Result.objects.filter(quiz_id=quiz_id, student=request.user).exists():
            for i in range(quiz.size()):
                result=Result.objects.create(quiz_id=quiz_id, student=request.user, pos=i+1)
                problem=quiz.problem_set.filter(quiz_id=quiz_id, order=i+1).order_by('?').first()
                result.problem=problem
                result.save()

    result = Result.objects.filter(quiz_id=quiz_id, pos=pos, student=request.user).first()
    results = Result.objects.filter(quiz_id=quiz_id, student=request.user).order_by('pos')

    if result and result.choice:
        choice = result.choice.id
    else:
        choice = None

    return render(request, 'quiz/main.html', {'problem': result.problem, 'user_choice': choice, 'results': results})


def quizEnd(request, quiz_id):
    quiz = Quiz.objects.get(pk=quiz_id)
    return render(request, 'quiz/end.html', {'quiz': quiz})


def problemsView(request, quiz_id):
    if request.user.is_staff:
        problems = Problem.objects.filter(quiz_id=quiz_id).order_by('order')
        return render(request, 'quiz/problems.html', {'problems': problems})
    else:
        return HttpResponse("handah erhgui bna.")


def pandasView(request, quiz_id):
    quiz=Quiz.objects.get(pk=quiz_id)
    pd.options.display.float_format = '{:,.2f}'.format

    with connection.cursor() as cursor:
        if quiz.quiz_type == 0:
           cursor.execute("select u.username, r.pos, a.points from quiz_result r join quiz_answerchoice a \
                       on r.choice_id=a.id join auth_user u on u.id=r.student_id where quiz_id=%s", [quiz_id])
        else:
            cursor.execute("select u.username, r.pos, r.score from quiz_result r \
                       join auth_user u on u.id=r.student_id where quiz_id=%s", [quiz_id])
        results = cursor.fetchall()
    data = pd.DataFrame(results)
    if data.empty:
        pivot = 'Өгөгдөл олдсонгүй!'
        describe = pivot
    else:
        pivot = data.pivot_table(index=[0], columns=[1], values=2, fill_value=0)
        pivot = pivot.reindex(sorted(pivot.columns), axis=1)
        pivot['Дүн'] = pivot.sum(axis=1)
        pivot = pivot.sort_values(by='Дүн', ascending=False)
        pivot.loc['Дундаж'] = pivot.mean()
        corr = pivot.corr()
        dun = 100*corr.iloc[[-1]]
        dun = dun.rename(index={'Дүн': 'ЯЧИ'})
        pivot = pivot.append(dun)
        pivot = pivot.to_html(index_names=False)
        describe = data.describe().to_html()

    context = {
        'df': data.to_html(),
        'describe': describe,
        'pivot': pivot
    }
    return render(request, 'quiz/pandas.html', context)


def cloneProblem(request, problem_id):
    problem = Problem.objects.get(pk=problem_id)
    new_problem = Problem.objects.create(statement=problem.statement)
    new_problem.quiz = problem.quiz
    new_problem.order = problem.order
    new_problem.save()
    for choice in problem.answerchoice_set.all():
        new_choice = AnswerChoice.objects.create(problem=new_problem)
        new_choice.label = choice.label
        new_choice.value = choice.value
        new_choice.points = choice.points
        new_choice.order = choice.order
        new_choice.save()
    return redirect('quiz_problems',problem.quiz.id)


def importStudents(request):
    students = [['Өлзийцогт.Энх', '17B1NUM0689', '88254920'],
        ['Золжаргал.Одт', '20B1NUM0379', '85355336'],
        ['Мөнхтавилан.Эрд', '17B1NUM0502', '90410922'],
        ['Номин-Эрдэнэ.Отг', '21B1NUM4058', ''],
        ['Алтансүх.Энх', '20B1NUM0906', '99776100'],
        ['Банзрагч.Сон', '20B1NUM2367', '95443330'],
        ['Батбаатар.Эрд', '18B1NUM0394', '80920015'],
        ['Бат-Эрдэнэ.Бат', '18B1NUM1691', '94096408'],
        ['Билгүүдэй.Бал', '19B1NUM0460', '97091111'],
        ['Билгүүн Бен.Бям', '19B1NUM0701', '94091885'],
        ['Болормаа.Бат', '20B1NUM2031', '99657524'],
        ['Бөхбилэг.Бан', '17B1NUM0519', '90761071'],
        ['Дорж.Хор', '18B1NUM1221', '95592142'],
        ['Манлай.Цог', '20B1NUM2066', '91202002'],
        ['Маргад.Бат', '20B1NUM1208', '88600413'],
        ['Мөнхцэцэг.Хад', '20B1NUM0214', '89935799'],
        ['Мөрөн.Бат', '21B1NUM0015', '95199680'],
        ['Мэндсайхан.Үнэ', '20B1NUM1146', '99728233'],
        ['Нурбек.Жал', '17B1NUM1200', '99418795'],
        ['Рэнцэндондог.Эрд', '20B1NUM0054', '9,549,502,690,505,020'],
        ['Самад.Цэв', '20B1NUM1987', '85654525'],
        ['Сүрэнхорол.Амг', '19B1NUM0200', '96099260'],
        ['Өсөхбаяр.Бат', '19B1NUM0798', '88429033'],
        ['Тогтуун.Одб', '19B1NUM0905', '99534036'],
        ['Түвшинтөгс.Эрд', '20B1NUM0448', '89894002'],
        ['Тэмүүлэн.Бат', '18B1NUM0037', '95345924'],
        ['Цэлмэг.Адъ', '17B1NUM3071', '80709079'],
        ['Чилүүгэн.Бям', '19B1NUM0277', '94354466'],
        ['Чингүн.Унд', '18B1NUM1049', '88811988'],
        ['Чингүүн.Дор', '20B1NUM2390', '88066365'],
        ['Чинсанчир.Оюу', '16B1SEAS1868', '99915991'],
        ['Энхмөнх.Орг', '20B1NUM0689', '88153198'],
        ['Хангал.Бая', '21B1NUM3783', '80980620'],
        ['Бямбаочир.Бат', '19B1NUM2103', '99608011'],
        ['Насантөгөлдөр.Ама', '20B1NUM0421', '95235756'],
        ['Өсөхбаяр.Цэн', '20B1NUM2837', '99991190'],
        ['Анужин.Дор', '20B1NUM2124', '94288008'],
        ['Ариунэрдэнэ.Дуг', '18B1NUM2388', '96361004'],
        ['Золбаяр.Цэн', '20B1NUM2599', '88184032'],
        ['Алтжин.Алт', '20B1NUM1999', '80444997'],
        ['Амарболд.Эрд', '19B1NUM0900', '99221133'],
        ['Анар.Рад', '19B1NUM0828', '94918064'],
        ['Ганболд.Шин', '20B1NUM2044', '85599609'],
        ['Дармаабазар.Ган', '19B1NUM1105', '94463049'],
        ['Мишээл.Раг', '18B1NUM1986', '80209423'],
        ['Өнөдэлгэр.Энх', '20B1NUM0673', '94449677'],
        ['Нямдаваа.Урт', '19B1NUM0928', '80639093'],
        ['Хишигбаяр.Бал', '17B1NUM2078', '99335671'],
        ['Цогбадрах.Ган', '20B1NUM0477', '95481029'],
        ['Элбэг.Дар', '20B1NUM2279', '99464130'],
        ['Энхжин.Оюу', '20B1NUM1909', '99533528'],
        ['Айгерим.Бол', '20B1NUM0499', '99667243'],
        ['Анхзаяа.Эрд', '20B1NUM2422', '88594181'],
        ['Бямбадорж.Лха', '19B1NUM0647', '80369011'],
        ['Жансауле.Дау', '20B1NUM1196', '85147517'],
        ['Марал.Ган', '20B1NUM2627', '99889054'],
        ['Монголжингоо.Энх', '16B1SAS3145', '94059111'],
        ['Нандин-Эрдэнэ.Дор', '20B1NUM3181', '80702795'],
        ['Өнөболд.Оюу', '19B1NUM0142', '94821174'],
        ['Тэмүүлэн.Эрх', '20B1NUM2379', '99063458'],
        ['Удвал.Цэв', '19B1NUM1895', '99453105'],
        ['Чимиддулам.Эрх', '18B1NUM0652', '89767282'],
        ['Энхбаяр.Ган', '20B1NUM2198', '98983103'],
        ['Энхжин.Ган', '20B1NUM0484', '86150440'],
        ['Зоригт.Эрд', '20B1NUM1202', '99197106'],
        ['Билгүүн.Олз', '20B1NUM0351', '99690988'],
        ['Энхсайхан.Энх', '20B1NUM2150', '94402411'],
        ['Сарнай.Мөн', '18B1NUM0370', '94615531'],
        ['Тэмүүжин.Чул', '18B1NUM0553', '80477017'],
        ['Цэрэнханд.Бат', '17B1NUM2417', '99952248'],
        ['Булганшагай.Мөн', '20B1NUM2568', '85566224'],
        ['Бэлгүдэй.Бол', '21B1NUM2491', '85851836'],
        ['Ихбаяр.Хүр', '21B1NUM3326', '95008877'],
        ['Туул.Бат', '21B1NUM0902', '95842814'],
        ['Энхманлай.Бат', '20B1NUM1895', '95688076'],
        ['Адъяабазар.Чой', '18B1NUM0651', '99908340'],
        ['Азжаргал.Ама', '20B1NUM1466', '95840145'],
        ['Амар.Бям', '19B1NUM1788', '88249795'],
        ['Бат-Уянга.Төр', '20B1NUM1591', '99602943'],
        ['Буджав.Бил', '18B1NUM0501', '89524810'],
        ['Бямбадорж.Бат', '20B1NUM0115', '80380733'],
        ['Бямбадулам.Сэр', '18B1NUM1587', '90533366'],
        ['Дашзэвэг.Ган', '20B1NUM2586', '95425170'],
        ['Мөнхмандах.Гал', '18B1NUM1253', '95356687'],
        ['Мөнхтүвшин.Бат', '19B1NUM2026', '88351606'],
        ['Нараа.Гүн', '18B1NUM0920', '80958587'],
        ['Отгонтөгс.Цэг', '20B1NUM1340', '85655035'],
        ['Эрдэнэбат.Мөн', '18B1NUM3460', '99132597'],
        ['Маралмаа.Алт', '20B1NUM1207', '80877211'],
        ['Эрдэнэбат.Ган', '20B1NUM1828', '99377196'],
        ['Ахтилек.Өми', '20B1NUM2008', '89428888'],
        ['Өсөх-Эрдэнэ.Энх', '19B1NUM0971', '88641198'],
        ['Энхмөнх.Мөн', '20B1NUM0489', '94399344']]

    for name, sisi, phone in students:
        s, created = User.objects.get_or_create(username=sisi)
        s.first_name = name
        s.last_name = phone
        s.username = sisi
        s.set_password(sisi)
        s.is_active = True
        m, created = UserMeta.objects.get_or_create(user=s)
        m.is_valid = True
        m.save()
        s.save()

    return HttpResponse("ok")


def resultsView(request, quiz_id):
    #return HttpResponse("not available")
    quiz = Quiz.objects.get(pk=quiz_id)
    with connection.cursor() as cursor:
        if quiz.quiz_type == 0:
            cursor.execute("select u.id, u.username, sum(ac.points) total \
                          from quiz_result r join quiz_answerchoice ac on r.`choice_id`=ac.id \
                          join auth_user u on u.id=r.`student_id` \
                          where r.quiz_id=%s group by u.id order by total desc", [quiz_id])
           # cursor.execute("select u.username, r.pos, a.points from quiz_result r join quiz_answerchoice a \
           #            on r.choice_id=a.id join auth_user u on u.id=r.student_id where quiz_id=%s", [quiz_id])
        else:
            cursor.execute("select u.id, u.username, sum(r.score) total from quiz_result r \
                       join auth_user u on u.id=r.student_id where quiz_id=%s \
                       group by u.id order by total desc", [quiz_id])
        results = cursor.fetchall()

    return render(request, 'quiz/results.html', {'results': results, 'quiz': quiz})


def studentResultView(request, student_id, quiz_id):
    results = Result.objects.filter(student_id=student_id, quiz_id=quiz_id).order_by('pos')
    student = User.objects.get(pk=student_id)
    quiz = Quiz.objects.get(pk=quiz_id)
    return render(request, 'quiz/student_result.html',
                  {'results': results, 'username': student.username, 'quiz': quiz})


@login_required
def exam_view(request, quiz_id):
    student_id=request.user.id
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            files = request.FILES.getlist('file')
            for f in files:
                upload = Upload(file=f,result_id=request.POST['result'])
                upload.save()

    quiz = Quiz.objects.get(pk=quiz_id)

    if not quiz.is_started() and not request.user.is_superuser:
        messages.info(request,'Шалгалт эхлээгүй байна.')
        return redirect('quiz_quizzes')

    if quiz.is_closed() and not request.user.is_superuser:
        messages.info(request, 'Шалгалтын хугацаа дууссан байна.')
        return redirect('quiz_quizzes')

    for pos in range(1,quiz.size()+1):
        result = Result.objects.get_or_create(student_id=student_id,quiz_id=quiz_id,pos=pos)
        if not result[0].problem:
            result[0].problem = quiz.problem_set.filter(quiz_id=quiz_id, order=pos).order_by('?').first()
            result[0].save()
    results = Result.objects.filter(student_id=student_id,quiz_id=quiz_id).order_by('pos')

    return render(request, 'quiz/exam.html', {'results': results})


def get(request):
    result_id = int(request.GET.get('result_id',0))
    if result_id > 0:
        result = Result.objects.get(pk=result_id)
        upload = Upload(result_id=result_id)
        form = UploadForm(instance=upload)
        return render(request,"quiz/form.html",{'form': form, 'result': result})
    else:
        return HttpResponse("Буруу хариулт")


@login_required
def grade(request):
    result_id = int(request.GET.get('result_id',0))
    if result_id > 0:
        result = Result.objects.get(pk=result_id)
        if request.method == 'POST':
            form = ResultsForm(request.POST, instance=result)
            if form.is_valid() and request.user.is_staff:
                form.save()
                url = reverse('quiz_exam_grading',args=[result.quiz_id])
                url = url + '#result{}'.format(result.id)
                return redirect(url)
        form = ResultsForm(instance=result)
        return render(request,"quiz/result_form.html",{'form': form, 'result': result})
    else:
        return HttpResponse("Ийм хариулт олдсонгүй.")


@login_required
def exam_grading_view(request,quiz_id):
    quiz=Quiz.objects.get(pk=quiz_id)

    results=Result.objects.filter(quiz_id=quiz_id).order_by('problem__order','problem_id','student__last_name')

    return render(request,'quiz/exam_results.html', {'results': results, 'quiz': quiz})


def resize_uploads():
    exception = 0
    uploads = Upload.objects.all()
    for upload in uploads:
        file = 'media/' + str(upload.file)
        try:
            size = os.path.getsize(file)
            print(size)
            if size > 1000000:
                img=Image.open(file)
                img.save(file,optimize=True,quality=50)
                print(file)
        except:
            exception = exception + 1

    return exception