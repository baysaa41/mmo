from django.http import HttpResponse, JsonResponse, FileResponse
from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.views.decorators.cache import cache_page
from accounts.models import UserMeta, Province, Zone
from olympiad.models import Olympiad, Problem, Result, Upload, SchoolYear, ScoreSheet
from posts.models import Post
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.forms import modelformset_factory
from .forms import ResultsForm, UploadForm, ResultsGraderForm
from datetime import datetime, timezone, timedelta

from django.contrib.auth.models import User
from django.contrib import messages

import openpyxl
from accounts.services import random_salt
from django.core.paginator import Paginator

from schools.models import School

ResultsFormSet = modelformset_factory(Result, form=ResultsForm, extra=0)


@login_required()
def index(request):
    now = datetime.now(timezone.utc)
    start = datetime.now(timezone.utc) + timedelta(hours=-5)
    end = datetime.now(timezone.utc) + timedelta(days=1)
    olympiads = Olympiad.objects.filter(start_time__gt=start, start_time__lte=end, level_id=request.user.data.level_id)

    return render(request, 'olympiad/index.html', {'olympiads': olympiads, 'now': now})


@login_required()
def supplement_home(request):
    olympiads = Olympiad.objects.filter(is_grading=True)
    # olympiads = {}

    return render(request, 'olympiad/supplement_home.html', {'olympiads': olympiads})


@login_required
def quiz_view(request, quiz_id):
    contestant = request.user
    olympiad = Olympiad.objects.filter(pk=quiz_id).first()

    if olympiad.group is not None:
        if contestant not in olympiad.group.user_set.all():
            message = "Зөвхөн '{}' бүлгийн сурагчид оролцох боломжтой".format(olympiad.group.name)
            messages.info(request, message)
            return redirect('olympiad_home')

    if not olympiad:
        messages.info(request, 'Олимпиад олдсонгүй.')
        return redirect('olympiad_home')

    if not olympiad.is_started():
        messages.info(request, 'Олимпиадын бодолт эхлээгүй байна.')
        return redirect('olympiad_home')

    if olympiad.is_finished():
        messages.info(request, 'Олимпиадын бодолт дууссан байна.')
        return redirect('olympiad_home')

    problems = olympiad.problem_set.order_by('order')
    user = request.user
    if not problems or not user.is_authenticated:
        return HttpResponse("Ops, something went wrong.")

    for problem in problems:
        result = Result.objects.get_or_create(contestant=user, olympiad_id=quiz_id, problem=problem)

    items = Result.objects.filter(contestant=user, olympiad_id=quiz_id).order_by('problem__order')

    if request.method == 'POST':
        if olympiad.is_closed():
            messages.error(request, 'Хариулт авах хугацаа дууссан.')
            return redirect('olympiad_quiz_end', quiz_id=quiz_id)
        form = ResultsFormSet(request.POST)
        if form.is_valid():
            form.save()
            results = Result.objects.filter(contestant=user, olympiad_id=quiz_id).order_by('problem__order')
            return render(request, 'olympiad/confirm.html', {'results': results, 'olympiad': olympiad})
    else:
        if olympiad.is_active():
            form = ResultsFormSet(
                queryset=Result.objects.filter(contestant=user, olympiad_id=quiz_id).order_by('problem__order'))
        else:
            messages.error(request, 'Хугацаа дууссан байна.')
            return redirect('olympiad_quiz_end', quiz_id=quiz_id)
    return render(request, 'olympiad/quiz.html', {'items': items, 'form': form, 'olympiad': olympiad})


@login_required
def quiz_end(request, quiz_id):
    quiz = Olympiad.objects.get(pk=quiz_id)
    return render(request, 'olympiad/end_note.html', {'quiz': quiz})


def mmo2021(request):
    return render(request, "accounts/site_home.html")


def post(request):
    id = int(request.GET.get('id', 0))
    mode = int(request.GET.get('mode', 0))
    if id > 0:
        article = Post.objects.filter(pk=id).first()
        return render(request, 'accounts/post.html', {'article': article, 'mode': mode})

@cache_page(60 * 60)
def problems_home(request):
    now = datetime.now(timezone.utc)
    mode = request.GET.get('mode', 0)
    school_year = SchoolYear.objects.filter(start__lt=now, end__gt=now).first()
    id = request.GET.get('year', school_year.id)
    year = SchoolYear.objects.filter(pk=id).first()
    prev = SchoolYear.objects.filter(pk=year.id - 1).first()
    next = SchoolYear.objects.filter(pk=year.id + 1).first()

    olympiads = Olympiad.objects.filter(is_open=True).order_by('-school_year_id', 'name', 'level')

    if id:
        olympiads = olympiads.filter(school_year=year)

    context = {
        'olympiads': olympiads,
        'year': year,
        'prev': prev,
        'next': next
    }
    return render(request, 'olympiad/problems_home.html', context=context)

@cache_page(60 * 60)
def problems_view(request, olympiad_id):
    probidden = [16, 17, 18, 19, 24, 25, 26]

    olympiad = Olympiad.objects.filter(pk=olympiad_id).first()

    try:
        mode = request.GET.get('mode', False)
        is_admin = request.user.is_superuser and mode
    except:
        is_admin = False

    if olympiad_id in probidden:
        problems = []
    elif olympiad:
        problems = olympiad.problem_set.order_by('order')
        if not olympiad.is_finished() and not is_admin:
            problems = []
    else:
        problems = []

    return render(request, 'olympiad/problems.html', {'olympiad': olympiad, 'problems': problems})


@login_required
def student_result_view(request, olympiad_id, contestant_id):
    results = Result.objects.filter(contestant_id=contestant_id, olympiad_id=olympiad_id).order_by('problem__order')
    contestant = User.objects.get(pk=contestant_id)
    olympiad = Olympiad.objects.get(pk=olympiad_id)
    username = contestant.last_name + ', ' + contestant.first_name
    return render(request, 'olympiad/student_result.html',
                  {'results': results, 'username': username, 'olympiad': olympiad})


@login_required
def exam_student_view(request, olympiad_id):
    contestant = request.user
    contestant_id = request.user.id
    olympiad = Olympiad.objects.filter(pk=olympiad_id).first()

    if olympiad.group is not None:
        if contestant not in olympiad.group.user_set.all():
            url = 'https://www.integral.mn/accounts/users/{}/'.format(olympiad.group.id)
            message = "Зөвхөн {} бүлгийн сурагчид оролцох боломжтой".format(olympiad.group.name)
            messages.info(request, message)
            return redirect('olympiad_home')

    if olympiad.is_active():
        if request.method == 'POST':
            form = UploadForm(request.POST, request.FILES)
            if form.is_valid():
                files = request.FILES.getlist('file')
                for f in files:
                    upload = Upload(file=f, result_id=request.POST['result'])
                    upload.result.state = 1
                    upload.result.save()
                    upload.save()

            return redirect('olympiad_exam', olympiad_id=olympiad_id)

        olympiad = Olympiad.objects.filter(pk=olympiad_id).first()
        if olympiad:
            problems = olympiad.problem_set.all().order_by('order')
            for problem in problems:
                Result.objects.get_or_create(contestant_id=contestant_id, olympiad_id=olympiad_id,
                                             problem_id=problem.id)

        results = Result.objects.filter(contestant_id=contestant_id, olympiad_id=olympiad_id).order_by('problem__order')

        return render(request, 'olympiad/exam.html',
                      {'results': results, 'olympiad': olympiad, 'contestant': contestant})
    elif not olympiad.is_started():
        messages.info(request, 'Бодолт эхлээгүй байна.')
        return redirect('olympiad_home')
    else:
        messages.info(request, 'Энэ олимпиадад оролцох эрхгүй байна.')
        return redirect('olympiad_home')


@login_required
def student_supplement_view(request, olympiad_id):
    # return HttpResponse("Nemelt material huleen avah hugatsaa duussan.")
    contestant = request.user
    contestant_id = request.user.id
    olympiad = Olympiad.objects.filter(pk=olympiad_id).first()

    if not olympiad.is_grading:
        return HttpResponse("Nemelt material huleen avah hugatsaa duussan.")
    if olympiad.group is not None:
        if contestant not in olympiad.group.user_set.all():
            message = "Зөвхөн '{}' бүлгийн сурагчид оролцох боломжтой".format(olympiad.group.name)
            messages.info(request, message)
            return redirect('olympiad_supplement_home')

    results = olympiad.result_set.filter(contestant=request.user)
    if not results and not request.user.is_staff:
        return HttpResponse("Zuvhun ene olympiadad oroltsson suragchid material nemj oruulah bolomjtoi.")

    if olympiad.is_grading:
        if request.method == 'POST':
            form = UploadForm(request.POST, request.FILES)
            if form.is_valid():
                files = request.FILES.getlist('file')
                for f in files:
                    upload = Upload(file=f, result_id=request.POST['result'])
                    upload.result.state = 3
                    upload.is_official = False
                    upload.result.save()
                    upload.save()

            return redirect('olympiad_supplements', olympiad_id=olympiad_id)

        olympiad = Olympiad.objects.filter(pk=olympiad_id).first()
        if olympiad:
            problems = olympiad.problem_set.all().order_by('order')
            for problem in problems:
                Result.objects.get_or_create(contestant_id=contestant_id, olympiad_id=olympiad_id,
                                             problem_id=problem.id)

        results = Result.objects.filter(contestant_id=contestant_id, olympiad_id=olympiad_id).order_by('problem__order')

        return render(request, 'olympiad/supplement_exam.html',
                      {'results': results, 'olympiad': olympiad, 'contestant': contestant})
    else:
        messages.info(request, 'Энэ олммпиадын засалт дууссан байна.')
        return redirect('olympiad_supplements', olympiad_id=olympiad_id)


@login_required
def exam_staff_view(request, olympiad_id, contestant_id):
    if request.user.is_staff:
        contestant = User.objects.get(pk=contestant_id)
        if request.method == 'POST':
            form = UploadForm(request.POST, request.FILES)
            if form.is_valid():
                files = request.FILES.getlist('file')
                for f in files:
                    upload = Upload(file=f, result_id=request.POST['result'])
                    upload.result.state = 3
                    upload.result.save()
                    upload.save()
            else:
                print("it is not valid!")
            return redirect('olympiad_exam_staff', olympiad_id=olympiad_id, contestant_id=contestant_id)

        olympiad = Olympiad.objects.filter(pk=olympiad_id).first()
        if olympiad:
            problems = olympiad.problem_set.all().order_by('order')
            for problem in problems:
                Result.objects.get_or_create(contestant_id=contestant_id, olympiad_id=olympiad_id,
                                             problem_id=problem.id)

        results = Result.objects.filter(contestant_id=contestant_id, olympiad_id=olympiad_id).order_by('problem__order')

        return render(request, 'olympiad/exam.html',
                      {'results': results, 'olympiad': olympiad, 'contestant': contestant})
    else:
        return HttpResponse("handah erhgui bna.")


@login_required
def quiz_staff_view(request, quiz_id, contestant_id):
    if not request.user.is_staff:
        return HttpResponse("Zasvartai")
    staff = request.user
    contestant = User.objects.get(pk=contestant_id)

    school = staff.moderating.all().first()
    #group = school.group

    #if not contestant.groups.filter(pk=group.id).exists():
    #    return render(request, 'error.html', {'error': 'Та зөвхөн өөрийн сургуулийн сурагчийн дүнг оруулах боломжтой.'})

    olympiad = Olympiad.objects.filter(pk=quiz_id).first()

    problems = olympiad.problem_set.order_by('order')
    user = request.user
    if not problems or not user.is_authenticated:
        return HttpResponse("Ops, something went wrong.")

    for problem in problems:
        result = Result.objects.get_or_create(contestant=contestant, olympiad_id=quiz_id, problem=problem)

    items = Result.objects.filter(contestant=contestant, olympiad_id=quiz_id).order_by('problem__order')

    if request.method == 'POST':
        form = ResultsFormSet(request.POST)
        if form.is_valid():
            form.save()
            results = Result.objects.filter(contestant=contestant, olympiad_id=quiz_id).order_by('problem__order')
            # return redirect('quiz_list_view', staff.moderating.first().id)
            return render(request, 'olympiad/confirm_teacher.html', {'results': results, 'olympiad': olympiad, 'contestant': contestant})
    else:
        form = ResultsFormSet(
            queryset=Result.objects.filter(contestant=contestant, olympiad_id=quiz_id).order_by('problem__order'))
    return render(request, 'olympiad/quiz.html', {'items': items, 'form': form,
                                                  'olympiad': olympiad, 'contestant': contestant})

def is_my_student(teacher_id,student_id):
    try:
        school = School.objects.get(user_id=teacher_id)
        if school.group.user_set.filter(id=student_id).exists():
            return True
    except:
        return False
    return False
@login_required
def quiz_staff_view2(request, quiz_id, contestant_id):
    if not request.user.is_staff:
        return HttpResponse("Zasvartai")
    staff = request.user
    contestant = User.objects.get(pk=contestant_id)

    try:
        olympiad = Olympiad.objects.get(pk=quiz_id)
    except Olympiad.DoesNotExist:
        return HttpResponse("Ops, something went wrong.")

    school = staff.moderating.all().first()
    group = school.group

    if not is_my_student(staff.id,contestant_id) and not staff.is_staff:
        return render(request, 'messages/../templates/schools/error.html', {'error': 'Та зөвхөн өөрийн сургуулийн сурагчийн дүнг оруулах боломжтой.'})

    if request.method == 'POST':
        keys = request.POST.keys()
        problems = list(keys)[2:]
        for problem in problems:
            id = int(problem[1:])
            result = Result.objects.get(pk=id)
            if request.POST[problem] == '':
                result.answer = None
            elif request.POST[problem] != 'None':
                result.answer = int(request.POST[problem])
            result.save()

    staff = request.user
    contestant = User.objects.get(pk=contestant_id)

    school = staff.moderating.first()

    problems = olympiad.problem_set.order_by('order')

    results = []
    for problem in problems:
        result, created = Result.objects.get_or_create(contestant=contestant, olympiad_id=quiz_id, problem=problem)
        results.append(result)

    return render(request, 'olympiad/quiz2.html', {'school': school,
                                                   'contestant': contestant,
                                                   'olympiad': olympiad,
                                                   'results': results})


def quiz_list_view(request, school_id):
    school = School.objects.get(pk=school_id)
    quizzes = Olympiad.objects.filter(is_open=True, is_grading=True)
    return render(request, 'schools/olympiad_list.html', {'contestants': school.group.user_set.all(),
                                                          'quizzes': quizzes})


def get_result_form(request):
    result_id = int(request.GET.get('result_id', 0))
    if result_id > 0:
        result = Result.objects.get(pk=result_id)
        upload = Upload(result_id=result_id)
        form = UploadForm(instance=upload)
        return render(request, "olympiad/form.html", {'form': form, 'result': result})
    else:
        return JsonResponse({'status': 'failed'})


def result_viewer(request):
    result_id = int(request.GET.get('result_id', 0))
    if result_id > 0:
        result = Result.objects.get(pk=result_id)
        if result.contestant_id == request.user.id:
            return render(request, "olympiad/result_view.html", {'result': result})

    return JsonResponse({'status': 'failed'})


# @login_required
def grading_home(request):
    olympiads = Olympiad.objects.filter(is_grading=True).order_by('id')

    return render(request, 'olympiad/grading_home.html', {'olympiads': olympiads})


@login_required
def exam_grading_view(request, problem_id):
    problem = Problem.objects.filter(pk=problem_id).first()
    if not request.user.is_staff:
        return render(request, 'messages/../templates/schools/error.html', {message: 'Хандах эрхгүй.'})

    results = Result.objects.filter(problem_id=problem_id, contestant__data__province__isnull=False).order_by(
        'score').reverse

    return render(request, 'olympiad/exam_grading.html', {'results': results, 'problem': problem})


@login_required
def grade(request):
    result_id = int(request.GET.get('result_id', 0))
    if result_id > 0:
        result = Result.objects.get(pk=result_id)
        if not result.olympiad.is_grading or result.state == 5:
            return HttpResponse("Энэ бодлогын үнэлгээг өөрчлөх боломжгүй.")
        if request.method == 'POST':
            form = ResultsGraderForm(request.POST, instance=result)
            if form.is_valid() and request.user.is_staff:
                form.save()
                result.coordinator = request.user
                result.state = 2
                result.save()
                url = reverse('olympiad_exam_grading', kwargs={'problem_id': result.problem.id})
                url = url + '#result{}'.format(result.id)
                return redirect(url)
        form = ResultsGraderForm(instance=result)
        return render(request, "olympiad/result_form.html", {'form': form, 'result': result})
    else:
        return HttpResponse("Ийм хариулт олдсонгүй.")

@login_required
def student_exam_materials_view(request):
    user_id = request.GET.get('user_id', request.user.id)
    results = Result.objects.filter(contestant_id=user_id)
    title = "ID: {}, {}, {} сурагчийн илгээсэн материалууд".format(request.user.id, request.user.first_name,
                                                                   request.user.last_name)

    return render(request, 'olympiad/exam_materials.html', {'results': results, 'title': title})


@login_required
def view_result(request):
    result_id = int(request.GET.get('result_id', 0))
    if result_id > 0:
        result = Result.objects.filter(pk=result_id).first()
        return render(request, "olympiad/upload_viewer.html", {'result': result})
    else:
        return HttpResponse("Ийм хариулт олдсонгүй.")


def problem_exam_materials_view(request):
    return None


def supplements_view(request):
    uploads = Upload.objects.filter(is_official=False).order_by('upload_time')
    return render(request, 'olympiad/supplements.html', {'uploads': uploads})


@login_required
def approve_supplement(request):
    id = request.GET.get('id', False)
    if id and request.user.is_superuser:
        upload = Upload.objects.filter(pk=id).first()
        upload.result.state = 3
        upload.result.save()
        upload.is_official = True
        upload.save()
        return JsonResponse({'msg': 'Оk.'})
    return JsonResponse({'msg': 'No uploads.'})


@login_required
def remove_supplement(request):
    id = request.GET.get('id', False)
    if id and request.user.is_superuser:
        upload = Upload.objects.filter(pk=id).first()
        upload.delete()
        return JsonResponse({'msg': 'Оk.'})
    return JsonResponse({'msg': 'No uploads.'})


def list_upcomming_olympiads(request):
    now = datetime.now(timezone.utc)
    start = datetime.now(timezone.utc) + timedelta(hours=-5)
    end = datetime.now(timezone.utc) + timedelta(days=1)
    olympiads = Olympiad.objects.exclude(end_time__lt=now).order_by('start_time')

    return render(request, 'olympiad/index.html', {'olympiads': olympiads, 'now': now})


def read_worksheet(worksheet, problems):
    aldaa = False
    excel_data = list()

    # iterating over the rows and
    # getting value from each cell in row
    ind = 0
    for row in worksheet.iter_rows():
        row_data = list()
        tailbar = list()

        if ind == 0:
            row_data = ['№', 'ID', 'Овог', 'Нэр', 'Дүүргийн код', 'Сургууль', 'Анги']
            row_org = []
            for cell in row[:7]:
                row_org.append(str(cell.value).strip())

            if row_data == row_org:
                for i in range(problems):
                    row_data.append(('№{}'.format(i + 1)))
                row_data.append('Тайлбар')
            else:
                aldaa = True
                print(1)
        else:
            for cell in row[:7]:
                if str(cell.value) == 'None':
                    row_data.append('')
                else:
                    row_data.append(str(cell.value))
            for cell in row[7:problems + 7]:
                if str(cell.value) == 'None':
                    row_data.append('')
                else:
                    try:
                        row_data.append(int(cell.value))
                    except ValueError:
                        row_data.append(cell.value)
                        tailbar.append('Бүхэл тоон хариулт биш')
                        aldaa = True
                    except Exception as e:
                        row_data.append(cell.value)
                        tailbar.append(str(e))
                        aldaa = True

            try:
                user = User.objects.get(pk=int(row[1].value))
            except User.DoesNotExist:
                tailbar.append('ID буруу')
            except TypeError as e:
                if str(row[2].value) != 'None' or str(row[3].value) != 'None':
                    print(row)
                    # tailbar.append('Шинээр хэрэглэгч үүсгэнэ. Засах шаардлагагүй.')
                else:
                    tailbar.append('Мэдээлэл дутуу')
                    aldaa = True
                    print(row[1])
                    print(str(e))
                    print(3)

            row_data.append(', '.join(tailbar))
        ind = ind + 1
        excel_data.append(row_data)

    return excel_data, aldaa


def set_answer(olympiad_id, excel_data):
    olympiad = Olympiad.objects.get(pk=olympiad_id)
    problems = olympiad.problem_set.all()
    for row in excel_data[1:]:
        print(row)
        for i in range(len(row[7:-1])):
            problem = problems.filter(order=i + 1).first()
            if row[1] == '' and (row[2] != '' or row[3] != ''):
                user, c = User.objects.get_or_create(username=random_salt(8),
                                                     first_name=row[3] + '-system',
                                                     last_name=row[2] + '-system',
                                                     email='mmo60official@gmail.com',
                                                     is_active=True)
                if c:
                    user.username = 'u' + str(user.id)
                    user.save()
                UserMeta.objects.get_or_create(user=user, province_id=row[4], school=row[5], grade_id=row[6])
                row[1] = user.id
            else:
                try:
                    row[1] = int(float(row[1]))
                except ValueError:
                    print(row)
                    pass

            answer, created = Result.objects.get_or_create(contestant_id=int(float(row[1])),
                                                           olympiad_id=olympiad_id,
                                                           problem_id=problem.id)

            answer.state = 2
            if row[i + 7] == '':
                row[i + 7] = 0
            answer.answer = int(row[i + 7])
            answer.save()
    return True


@staff_member_required
def upload_file(request):
    if "GET" == request.method:
        context = {'error': 0}
        return render(request, 'olympiad/upload_file.html', context)
    else:
        aldaa = False
        excel_file = request.FILES["excel_file"]

        # you may put validations here to check extension or file size

        wb = openpyxl.load_workbook(excel_file)

        try:
            worksheet = wb["C (5-6)"]
        except:
            worksheet = wb["5-6"]
        excel_data_c, c = read_worksheet(worksheet, 10)

        # getting a particular sheet by name out of many sheets
        try:
            worksheet = wb["D (7-8)"]
        except:
            worksheet = wb["7-8"]
        excel_data_d, d = read_worksheet(worksheet, 10)

        try:
            worksheet = wb["E (9-10)"]
        except:
            worksheet = wb["9-10"]
        excel_data_e, e = read_worksheet(worksheet, 12)

        # getting a particular sheet by name out of many sheets
        try:
            worksheet = wb["F (11-12)"]
        except:
            worksheet = wb["11-12"]
        excel_data_f, f = read_worksheet(worksheet, 12)

        aldaa = aldaa or c or d or e or f

        if not aldaa:
            set_answer(137, excel_data_c)
            set_answer(138, excel_data_d)
            set_answer(139, excel_data_e)
            set_answer(140, excel_data_f)
            error = 1
        else:
            error = 2

        context = {"excel_data_c": excel_data_c, "excel_data_d": excel_data_d, "excel_data_e": excel_data_e,
                   "excel_data_f": excel_data_f, 'error': error}

        return render(request, 'olympiad/upload_file.html', context)


#@login_required
def olympiad_scores(request, olympiad_id):
    province_id = request.GET.get('p', '0')
    zone_id = request.GET.get('z', '0')
    page_number = request.GET.get('page', '1')
    size = 1000

    olympiad = get_object_or_404(Olympiad, id=olympiad_id)

    # Get current user's score, if available
    user_score_data = None
    if request.user.is_authenticated:
        try:
            user_scoresheet = ScoreSheet.objects.get(olympiad=olympiad, user=request.user)
            user_score_data = {
                'list_rank': user_scoresheet.list_rank,
                'last_name': user_scoresheet.user.last_name,
                'first_name': user_scoresheet.user.first_name,
                'id': user_scoresheet.user.id,
                'total': user_scoresheet.total,
                'ranking_a': user_scoresheet.ranking_a,
                'ranking_b': user_scoresheet.ranking_b,
            }
        except ScoreSheet.DoesNotExist:
            user_score_data = None

    # Filter based on province or zone, or get all scoresheets
    is_province = False
    is_zone = False
    if province_id != '0':
        scoresheets = ScoreSheet.objects.filter(
            olympiad=olympiad,
            user__data__province_id=province_id
        ).order_by("list_rank_p")
        province = Province.objects.get(pk=province_id)
        page_title = province.name
        is_province = True
    elif zone_id != '0':
        scoresheets = ScoreSheet.objects.filter(
            olympiad=olympiad,
            user__data__province__zone_id=zone_id
        ).order_by("list_rank_z")
        zone = Zone.objects.get(pk=zone_id)
        page_title = zone.name
        is_zone = True
    else:
        page_title = 'Бүх оролцогч'
        scoresheets = ScoreSheet.objects.filter(
            olympiad=olympiad
        ).order_by("list_rank")

    # Paginate scoresheets
    paginator = Paginator(scoresheets, size)
    scoresheets_page = paginator.get_page(page_number)

    # Prepare score data for each ScoreSheet
    score_data = []
    if is_province:
        for scoresheet in scoresheets_page:
            scores = [getattr(scoresheet, f's{i}', None) for i in range(1, olympiad.problem_set.count() + 1)]
            try:
                score_data.append({
                    'list_rank': scoresheet.list_rank_p,
                    'last_name': scoresheet.user.last_name,
                    'first_name': scoresheet.user.first_name,
                    'id': scoresheet.user.id,
                    'province': scoresheet.user.data.province.name,
                    'school': scoresheet.user.data.school,
                    'scores': scores,
                    'total': scoresheet.total,
                    'ranking_a': scoresheet.ranking_a_p,
                    'ranking_b': scoresheet.ranking_b_p,
                    'prizes': scoresheet.prizes,
                })
            except Exception as e:
                score_data.append({
                    'list_rank': scoresheet.list_rank_p,
                    'last_name': scoresheet.user.last_name,
                    'first_name': scoresheet.user.first_name,
                    'id': scoresheet.user.id,
                    'province': '',
                    'school': '',
                    'scores': scores,
                    'total': scoresheet.total,
                    'ranking_a': scoresheet.ranking_a_p,
                    'ranking_b': scoresheet.ranking_b_p,
                    'prizes': scoresheet.prizes,
                })
                print(e, scoresheet.user.id)
    elif is_zone:
        for scoresheet in scoresheets_page:
            scores = [getattr(scoresheet, f's{i}', None) for i in range(1, olympiad.problem_set.count() + 1)]
            try:
                score_data.append({
                    'list_rank': scoresheet.list_rank_z,
                    'last_name': scoresheet.user.last_name,
                    'first_name': scoresheet.user.first_name,
                    'id': scoresheet.user.id,
                    'province': scoresheet.user.data.province.name,
                    'school': scoresheet.user.data.school,
                    'scores': scores,
                    'total': scoresheet.total,
                    'ranking_a': scoresheet.ranking_a_z,
                    'ranking_b': scoresheet.ranking_b_z,
                    'prizes': scoresheet.prizes,
                })
            except Exception as e:
                score_data.append({
                    'list_rank': scoresheet.list_rank_z,
                    'last_name': scoresheet.user.last_name,
                    'first_name': scoresheet.user.first_name,
                    'id': scoresheet.user.id,
                    'province': '',
                    'school': '',
                    'scores': scores,
                    'total': scoresheet.total,
                    'ranking_a': scoresheet.ranking_a_z,
                    'ranking_b': scoresheet.ranking_b_z,
                    'prizes': scoresheet.prizes,
                })
                print(e, scoresheet.user.id)
    else:
        for scoresheet in scoresheets_page:
            scores = [getattr(scoresheet, f's{i}', None) for i in range(1, olympiad.problem_set.count() + 1)]
            # print(scores)
            try:
                score_data.append({
                    'list_rank': scoresheet.list_rank,
                    'last_name': scoresheet.user.last_name,
                    'first_name': scoresheet.user.first_name,
                    'id': scoresheet.user.id,
                    'province': scoresheet.user.data.province.name,
                    'school': scoresheet.user.data.school,
                    'scores': scores,
                    'total': scoresheet.total,
                    'ranking_a': scoresheet.ranking_a,
                    'ranking_b': scoresheet.ranking_b,
                    'prizes': scoresheet.prizes,
                })
            except Exception as e:
                score_data.append({
                    'list_rank': scoresheet.list_rank,
                    'last_name': scoresheet.user.last_name,
                    'first_name': scoresheet.user.first_name,
                    'id': scoresheet.user.id,
                    'province': '',
                    'school': '',
                    'scores': scores,
                    'total': scoresheet.total,
                    'ranking_a': scoresheet.ranking_a,
                    'ranking_b': scoresheet.ranking_b,
                    'prizes': scoresheet.prizes,
                })
                print(e, scoresheet.user.id)
    if is_province:
        title = ''
    context = {
        'page_title': page_title,
        'olympiad': olympiad,
        'user_score_data': user_score_data,
        'score_data': score_data,
        'problem_range': range(1, olympiad.problem_set.count() + 1),
        'paginator': paginator,
        'page_obj': scoresheets_page,
        'is_province': is_province,
    }
    return render(request, 'olympiad/olympiad_scores.html', context)