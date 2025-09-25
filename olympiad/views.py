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
from accounts.utils import random_salt
from django.core.paginator import Paginator
from django.db.models import Count

from schools.models import School

ResultsFormSet = modelformset_factory(Result, form=ResultsForm, extra=0)


@login_required
def olympiad_top_stats(request, olympiad_id):
    olympiad = get_object_or_404(Olympiad, id=olympiad_id)
    province_id = request.GET.get("p", "0").strip()
    zone_id = request.GET.get("z", "0").strip()

    scoresheets = ScoreSheet.objects.filter(olympiad=olympiad, total__gt=0)

    # --- аль ranking багана ашиглахыг шийдэх ---
    if province_id != "0":
        scoresheets = scoresheets.filter(user__data__province_id=province_id)
        rank_field = "ranking_a_p"
    elif zone_id != "0":
        scoresheets = scoresheets.filter(user__data__province__zone_id=zone_id)
        rank_field = "ranking_a_z"
    else:
        rank_field = "ranking_a"

    scoresheets = scoresheets.order_by(rank_field)

    if olympiad.level.id in [2,3,4,5]:
        # Эхний 50 ба эхний 30-г тасалж авах
        top50 = scoresheets.filter(**{f"{rank_field}__lte": 50})
        top30 = scoresheets.filter(**{f"{rank_field}__lte": 30})
        top_name_50 = '50'
        top_name_30 = '30'
    else:
        top50 = scoresheets.filter(**{f"{rank_field}__lte": 30})
        top30 = scoresheets.filter(**{f"{rank_field}__lte": 10})
        top_name_50 = '30'
        top_name_30 = '10'

    # --- Нэмэлтээр нийт тоог авах ---
    top50_count = top50.count()
    top30_count = top30.count()

    # Статистикууд
    top50_by_school = top50.values("school__name").annotate(count=Count("id")).order_by("-count")
    top30_by_province = top30.values("user__data__province__name").annotate(count=Count("id")).order_by("-count")
    top30_by_zone = top30.values("user__data__province__zone__name").annotate(count=Count("id")).order_by("-count")

    context = {
        "olympiad": olympiad,
        "top50_by_school": top50_by_school,
        "top30_by_province": top30_by_province,
        "top30_by_zone": top30_by_zone,
        "selected_province": province_id,
        "selected_zone": zone_id,
        "rank_field": rank_field,
        "top50_count": top50_count,
        "top30_count": top30_count,
        "top_name_50": top_name_50,
        "top_name_30": top_name_30,
    }
    return render(request, "olympiad/olympiad_top_stats.html", context)





@login_required()
def index(request):
    now = datetime.now(timezone.utc)
    start = datetime.now(timezone.utc) + timedelta(hours=-5)
    end = datetime.now(timezone.utc) + timedelta(days=1)
    olympiads = Olympiad.objects.filter(start_time__gt=start, start_time__lte=end, level_id=request.user.data.level_id)

    return render(request, 'olympiad/home.html', {'olympiads': olympiads, 'now': now})


@login_required()
def supplement_home(request):
    olympiads = Olympiad.objects.filter(is_grading=True)
    # olympiads = {}

    return render(request, 'olympiad/supplement_home.html', {'olympiads': olympiads})


@login_required
def quiz_end(request, quiz_id):
    quiz = Olympiad.objects.get(pk=quiz_id)
    return render(request, 'olympiad/end_note.html', {'quiz': quiz})


@login_required
def student_result_view(request, olympiad_id, contestant_id):
    results = Result.objects.filter(contestant_id=contestant_id, olympiad_id=olympiad_id).order_by('problem__order')
    contestant = User.objects.get(pk=contestant_id)
    olympiad = Olympiad.objects.get(pk=olympiad_id)
    username = contestant.last_name + ', ' + contestant.first_name
    return render(request, 'olympiad/results/student_result.html',
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

        return render(request, 'olympiad/olympiad_exam_view.html',
                      {'results': results, 'olympiad': olympiad, 'contestant': contestant})
    elif not olympiad.is_started():
        messages.info(request, 'Бодолт эхлээгүй байна.')
        return redirect('olympiad_home')
    else:
        messages.info(request, 'Энэ олимпиадад оролцох эрхгүй байна.')
        return redirect('olympiad_home')


def is_my_student(teacher_id,student_id):
    try:
        school = School.objects.get(user_id=teacher_id)
        if school.group.user_set.filter(id=student_id).exists():
            return True
    except:
        return False
    return False

@login_required
def quiz_staff_view(request, olympiad_id, contestant_id):
    if not request.user.is_staff:
        return render(request, "error.html", {'message': 'Хандах эрхгүй.'})

    staff = request.user
    contestant = User.objects.get(pk=contestant_id)

    try:
        olympiad = Olympiad.objects.get(pk=olympiad_id)
    except Olympiad.DoesNotExist:
        return HttpResponse("Ops, something went wrong.")

    school = staff.moderating.all().first()
    group = school.group

    if not is_my_student(staff.id,contestant_id) and not staff.is_staff:
        return render(request, 'error.html', {'error': 'Та зөвхөн өөрийн сургуулийн сурагчийн дүнг оруулах боломжтой.'})

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
        result, created = Result.objects.get_or_create(contestant=contestant, olympiad_id=olympiad_id, problem=problem)
        results.append(result)

    return render(request, 'olympiad/quiz/staff_edit.html', {'school': school,
                                                   'contestant': contestant,
                                                   'olympiad': olympiad,
                                                   'results': results})


def get_result_form(request):
    result_id = int(request.GET.get('result_id', 0))
    if result_id > 0:
        result = Result.objects.get(pk=result_id)
        upload = Upload(result_id=result_id)
        form = UploadForm(instance=upload)
        return render(request, "olympiad/upload_form.html", {'form': form, 'result': result})
    else:
        return JsonResponse({'status': 'failed'})


def result_viewer(request):
    # needs fix
    result_id = int(request.GET.get('result_id', 0))
    result = get_object_or_404(Result, pk=result_id)
    if result_id > 0:
        return render(request, "olympiad/results/result_view.html", {'result': result})

    return JsonResponse({'status': 'failed'})


@staff_member_required
def grading_home(request):
    olympiads = Olympiad.objects.filter(is_grading=True).order_by('id')

    return render(request, 'olympiad/grading_home.html', {'olympiads': olympiads})


@staff_member_required
def exam_grading_view(request, problem_id):
    problem = Problem.objects.filter(pk=problem_id).first()

    results = Result.objects.filter(problem_id=problem_id, contestant__data__province__isnull=False).order_by(
        'score').reverse

    return render(request, 'olympiad/exam_grading.html', {'results': results, 'problem': problem})


@staff_member_required
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
        return render(request, "olympiad/grading_result_form.html", {'form': form, 'result': result})
    else:
        return HttpResponse("Ийм хариулт олдсонгүй.")

@login_required
def student_exam_materials_view(request):
    user_id = request.GET.get('user_id', request.user.id)
    results = Result.objects.filter(contestant_id=user_id)
    title = "ID: {}, {}, {} сурагчийн илгээсэн материалууд".format(request.user.id, request.user.first_name,
                                                                   request.user.last_name)

    return render(request, 'olympiad/student_exam_materials_view.html', {'results': results, 'title': title})


@login_required
def view_result(request):
    result_id = int(request.GET.get('result_id', 0))
    if result_id > 0:
        result = Result.objects.filter(pk=result_id).first()
        return render(request, "olympiad/upload_viewer.html", {'result': result})
    else:
        return HttpResponse("Ийм хариулт олдсонгүй.")




