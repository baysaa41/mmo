from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db import connection
import pandas as pd

from .models import Quiz, Problem, UserAnswer

# Create your views here.

def index(request):
    quizzes = Quiz.objects.all()
    return render(request, 'myquiz/index.html', {'quizzes': quizzes})


def get_problems_with_answer(quiz_id, user_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM myquiz_problem p LEFT JOIN myquiz_useranswer a on p.id=a.problem_id \
        WHERE p.quiz_id = %s and a.user_id = %s", [quiz_id, user_id])
        rows = cursor.fetchall()
    connection.close()

    return rows


def check_quiz(request):
    id = request.GET.get('id',0)
    quiz = Quiz.objects.filter(pk=id).first()

    if quiz.is_active():
        return JsonResponse({'status': 1})

    if not request.user.is_authenticated:
        return JsonResponse({'status': 0, 'msg': 'Хэрэглэгч нэвтрээгүй байна.'})

    if not quiz:
        return JsonResponse({'status': 0, 'msg': 'Тест олдсонгүй.'})

    if request.user.data.grade.id > quiz.max_grade:
        return JsonResponse({'status': 0, 'msg': 'Анги тохирохгүй байна.'})

    if request.user.data.grade.id < quiz.min_grade:
        return JsonResponse({'status': 0, 'msg': 'Анги тохирохгүй байна.'})

    if quiz.is_active():
        return JsonResponse({'status': 1})

    if quiz.is_finished():
        return JsonResponse({'status': 0, 'msg': 'Хугацаа дууссан.'})

    if not quiz.is_started():
        return JsonResponse({'status': 0, 'msg': 'Тест эхлээгүй.'})

    return JsonResponse({'status': 0, 'msg': 'Алдаа гарлаа.'})


def clear_all(request):
    quiz_id = request.GET.get('qid', 0)
    user_id = request.GET.get('uid', 0)
    answers = UserAnswer.objects.filter(problem__quiz_id=quiz_id,user_id=user_id)
    quiz = Quiz.objects.filter(pk=quiz_id).first()

    if answers and quiz and quiz.is_active():
        for answer in answers:
            answer.answer = 0
            answer.save()
        return JsonResponse({"status": 1})
    elif quiz.is_finished():
        return JsonResponse({'status': 0, 'msg': 'Хугацаа дууссан.'})
    elif not quiz.is_started():
        return JsonResponse({'status': 0, 'msg': 'Тест эхлээгүй.'})
    else:
        return JsonResponse({'status': 0, 'msg': 'Алдаа гарлаа.'})


@login_required
def start_quiz(request,quiz_id):
    quiz = Quiz.objects.filter(pk=quiz_id).first()

    if not quiz:
        return JsonResponse({'status': 0, 'msg': 'Тест олдохгүй байна.'})

    if not request.user.data.province_id == 3:
        return JsonResponse({'status': 0, 'msg': 'Зөвхөн Баянхонгор аймгийн багш, сурагчид оролцоно.'})


    #if not request.user.is_superuser:
    if request.user.data.grade.id > quiz.max_grade:
        return JsonResponse({'status': 0, 'msg': 'Буруу ангилал.'})

    if request.user.data.grade.id < quiz.min_grade:
        return JsonResponse({'status': 0, 'msg': 'Буруу ангилал.'})

    if not quiz and not quiz.is_active() and not request.user.is_superuser:
        return redirect("/oidov/")

    quiz_problems = quiz.problem_set.all().order_by("order")
    for problem in quiz_problems:
        UserAnswer.objects.get_or_create(problem_id=problem.id,user_id=request.user.id)
    problems = get_problems_with_answer(quiz_id,request.user.id)
    return render(request,'myquiz/quiz.html',{'quiz': quiz, 'problems': problems})


def save_answer(request):
    pid = request.GET.get('pid', 0)
    uid = request.GET.get('uid', 0)
    choice = request.GET.get('choice', 0)

    is_valid = pid and uid and choice

    problem = Problem.objects.filter(pk=pid).first()

    if is_valid and problem and (problem.quiz.is_active() or request.user.is_superuser):
        answer, create = UserAnswer.objects.get_or_create(problem_id=pid,user_id=uid)
        answer.answer = choice
        answer.save()
        return JsonResponse({'status': 1})

    elif not problem.quiz.is_active() and not request.user.is_superuser:

        return JsonResponse({'status': 0, 'msg': 'Тест хугацаа тохирооогүй.'})

    return JsonResponse({'status': 0, 'msg': 'Алдаа гарсан.'})


def pandasView(request, quiz_id):
    quiz = Quiz.objects.filter(pk=quiz_id).first()
    pd.options.display.float_format = '{:,.2f}'.format

    with connection.cursor() as cursor:
        cursor.execute('''select u.first_name, p.`order`, r.score, r.answer, u.last_name, g.name, u.id \
        from myquiz_useranswer r join auth_user u on r.`user_id`=u.id \
        join accounts_usermeta m on m.user_id=u.id join accounts_grade g on g.id=m.grade_id \
        join myquiz_problem p on r.`problem_id`=p.id where p.quiz_id=%s''', [quiz_id])
        results = cursor.fetchall()
    data = pd.DataFrame(results)
    if data.empty:
        pivot = 'Өгөгдөл олдсонгүй!'
        describe = pivot
    else:
        pivot = data.pivot_table(index=[0,4,5,6], columns=[1], values=[2], fill_value=0)
        pivot = pivot.reindex(sorted(pivot.columns), axis=1)
        pivot['Дүн'] = pivot.sum(axis=1)
        pivot = pivot.sort_values(by='Дүн', ascending=False)
        pivot.loc['Дундаж'] = pivot.mean()
        corr = pivot.corr()
        dun = 100 * corr.iloc[[-1]]
        dun = dun.rename(index={'Дүн': 'ЯЧИ'})
        pivot = pivot.append(dun)
        pivot = pivot.to_html(index_names=False)
        describe = data.describe().to_html()

    context = {
        'df': data.to_html(index=False),
        'describe': describe,
        'pivot': pivot,
        'quiz': quiz,
    }
    return render(request, 'myquiz/../templates/olympiad/pandas3.html', context)