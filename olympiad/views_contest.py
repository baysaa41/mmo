from django.http import HttpResponse, JsonResponse, FileResponse
from django.shortcuts import render, redirect, reverse, get_object_or_404
from olympiad.models import Olympiad, Problem, Result, Upload, SchoolYear, ScoreSheet
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.forms import modelformset_factory
from .forms import ResultsForm, UploadForm, ResultsGraderForm
from datetime import datetime, timezone, timedelta

from django.contrib.auth.models import User
from django.contrib import messages

from django.db.models import Count

from schools.models import School

ResultsFormSet = modelformset_factory(Result, form=ResultsForm, extra=0)

@login_required()
def supplement_home(request):
    olympiads = Olympiad.objects.filter(is_grading=True)
    # olympiads = {}

    return render(request, 'olympiad/supplement_home.html', {'olympiads': olympiads})

@login_required
def quiz_view(request, olympiad_id):
    contestant = request.user
    olympiad = Olympiad.objects.filter(pk=olympiad_id).first()

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
        result = Result.objects.get_or_create(contestant=user, olympiad_id=olympiad_id, problem=problem)

    items = Result.objects.filter(contestant=user, olympiad_id=olympiad_id).order_by('problem__order')

    if request.method == 'POST':
        if olympiad.is_closed():
            messages.error(request, 'Хариулт авах хугацаа дууссан.')
            return redirect('olympiad__end', olympiad_id=olympiad_id)
        form = ResultsFormSet(request.POST)
        if form.is_valid():
            form.save()
            results = Result.objects.filter(contestant=user, olympiad_id=olympiad_id).order_by('problem__order')
            return render(request, 'olympiad/quiz_view_confirm.html', {'results': results, 'olympiad': olympiad})
    else:
        if olympiad.is_active():
            form = ResultsFormSet(
                queryset=Result.objects.filter(contestant=user, olympiad_id=olympiad_id).order_by('problem__order'))
        else:
            messages.error(request, 'Хугацаа дууссан байна.')
            return redirect('olympiad_end', olympiad_id=olympiad_id)
    return render(request, 'olympiad/quiz.html', {'items': items, 'form': form, 'olympiad': olympiad})


@login_required
def olympiad_end(request, olympiad_id):
    olympiad = Olympiad.objects.get(pk=olympiad_id)
    return render(request, 'olympiad/exam/end_note.html', {'olympiad': olympiad})





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

        return render(request, 'olympiad/exam/exam.html',
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
                    upload.is_accepted = False
                    upload.result.save()
                    upload.save()

            return redirect('student_supplement_view', olympiad_id=olympiad_id)

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

def is_my_student(teacher_id,student_id):
    try:
        school = School.objects.get(user_id=teacher_id)
        if school.group.user_set.filter(id=student_id).exists():
            return True
    except:
        return False
    return False

@login_required
def quiz_staff_view(request, quiz_id, contestant_id):
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


# @login_required
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


def problem_exam_materials_view(request):
    return None




@login_required
def remove_supplement(request):
    id = request.GET.get('id', False)
    if id and request.user.is_superuser:
        upload = Upload.objects.filter(pk=id).first()
        upload.delete()
        return JsonResponse({'msg': 'Оk.'})
    return JsonResponse({'msg': 'No uploads.'})