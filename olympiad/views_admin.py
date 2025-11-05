from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Avg, Max, Min
from django.core.paginator import Paginator
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth.models import User

from .models import Olympiad, ScoreSheet, Result, SchoolYear, Upload, Problem, Topic
from .forms import ChangeScoreSheetSchoolForm, ResultsGraderForm, UploadForm

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

@require_POST
@csrf_exempt  # production-д бол csrf token ашиглаарай
def toggle_problem_topic(request, problem_id, topic_id):
    try:
        problem = Problem.objects.get(pk=problem_id)
        topic = Topic.objects.get(pk=topic_id)

        if topic in problem.topics.all():
            problem.topics.remove(topic)
            action = "removed"
        else:
            problem.topics.add(topic)
            action = "added"

        return JsonResponse({
            "status": "ok",
            "action": action,
            "topic": topic.name,
            "problem_id": problem.id,
        })
    except Problem.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Problem not found"}, status=404)
    except Topic.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Topic not found"}, status=404)


@login_required
def results_home(request):
    now = timezone.now()
    mode = request.GET.get('mode', 0)

    school_year = SchoolYear.objects.filter(start__lt=now, end__gt=now).first()
    id = request.GET.get('year', school_year.id if school_year else None)
    year = SchoolYear.objects.filter(pk=id).first() if id else None
    prev = SchoolYear.objects.filter(pk=year.id - 1).first() if year else None
    next = SchoolYear.objects.filter(pk=year.id + 1).first() if year else None

    olympiads = Olympiad.objects.filter(is_open=True).order_by('-school_year_id', 'name', 'level')

    if id:
        olympiads = olympiads.filter(school_year=year)

    context = {
        'olympiads': olympiads,
        'year': year,
        'prev': prev,
        'next': next
    }
    return render(request, 'olympiad/results/home.html', context=context)


@login_required
def olympiad_scores(request, olympiad_id):
    olympiad = get_object_or_404(Olympiad, pk=olympiad_id)
    scores = Result.objects.filter(problem__olympiad=olympiad).select_related("contestant", "problem")

    paginator = Paginator(scores, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "olympiad/results/olympiad_id.html", {
        "olympiad": olympiad,
        "scores": page_obj,
    })


@login_required
def problem_stats_view(request, problem_id):
    problem = get_object_or_404(Problem, pk=problem_id)
    results = Result.objects.filter(problem=problem, score__isnull=False)

    grouped = (results.values('score')
               .annotate(score_count=Count('score'))
               .order_by('score'))

    stats = results.aggregate(
        avg=Avg('score'),
        max=Max('score'),
        min=Min('score'),
        submissions=Count('id')
    )

    context = {
        "problem": problem,
        "grouped": grouped,
        "stats": stats,
    }
    return render(request, "olympiad/results/problem_stats.html", context)

@login_required
def olympiad_problem_stats(request, olympiad_id):
    cache_key = f"olympiad_stats_{olympiad_id}"
    data = cache.get(cache_key)

    if not data:
        olympiad = get_object_or_404(Olympiad, pk=olympiad_id)
        problems = olympiad.problem_set.order_by('order')

        problem_stats = []
        for problem in problems:
            results = Result.objects.filter(problem=problem, score__isnull=False)
            stats = results.aggregate(
                submissions=Count('id'),
                avg=Avg('score'),
                max=Max('score'),
                min=Min('score')
            )

            province_stats = []
            for prov in olympiad.schoolyear.province_set.all().order_by("id"):
                prov_results = results.filter(contestant__data__province=prov)
                total = prov_results.count()
                gt_zero = prov_results.filter(score__gt=0).count()
                full = prov_results.filter(score=problem.max_score).count()

                province_stats.append({
                    "province": prov.name,
                    "total": total,
                    "gt_zero": gt_zero,
                    "full": full,
                })

            problem_stats.append({
                "problem": problem,
                "stats": stats,
                "province_stats": province_stats,
            })

        data = {
            "olympiad": olympiad,
            "problem_stats": problem_stats,
        }
        cache.set(cache_key, data, timeout=None)

    return render(request, "olympiad/results/olympiad_problem_stats.html", data)


@staff_member_required
def scoresheet_change_school(request, scoresheet_id):
    sheet = get_object_or_404(ScoreSheet, pk=scoresheet_id)

    if request.method == "POST":
        form = ChangeScoreSheetSchoolForm(request.POST)
        if form.is_valid():
            sheet.school = form.cleaned_data["school"]
            sheet.prizes = form.cleaned_data.get("prizes", "")
            sheet.save()
            return redirect("olympiad_result_view", olympiad_id=sheet.olympiad_id)
    else:
        form = ChangeScoreSheetSchoolForm(initial={
            "province": sheet.school.province if sheet.school else None,
            "school": sheet.school,
            "prizes": sheet.prizes,
        })

    return render(request, "olympiad/admin/change_scoresheet_school.html", {
        "form": form,
        "sheet": sheet,
    })


@staff_member_required
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

        return render(request, 'olympiad/exam/exam.html',
                      {'results': results, 'olympiad': olympiad, 'contestant': contestant})
    else:
        return render(request, 'error.html', {'message':'Хандах эрхгүй.'})

@staff_member_required
def staff_supplements_view(request):
    uploads = Upload.objects.filter(is_accepted=False, is_supplement=True).order_by('upload_time')
    return render(request, 'olympiad/admin/supplements.html', {'uploads': uploads})


@staff_member_required
def approve_supplement(request):
    id = request.GET.get('id', False)
    if id and request.user.is_superuser:
        upload = Upload.objects.filter(pk=id).first()
        upload.result.state = 3
        upload.result.save()
        upload.is_accepted = True
        upload.save()
        return JsonResponse({'msg': 'Оk.'})
    return JsonResponse({'msg': 'No uploads.'})

@staff_member_required
def remove_supplement(request):
    id = request.GET.get('id', False)
    if id and request.user.is_superuser:
        upload = Upload.objects.filter(pk=id).first()
        upload.delete()
        return JsonResponse({'msg': 'Оk.'})
    return JsonResponse({'msg': 'No uploads.'})


@login_required
def view_result(request):
    result_id = int(request.GET.get('result_id', 0))
    if result_id > 0:
        result = Result.objects.filter(pk=result_id).first()
        return render(request, "olympiad/upload_viewer.html", {'result': result})
    else:
        return HttpResponse("Ийм хариулт олдсонгүй.")

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

@staff_member_required
def update_results(request, olympiad_id):
    # create_results(olympiad_id)
    # return HttpResponse('Edit update')
    olympiad = Olympiad.objects.filter(pk=olympiad_id, type=1).first()
    if olympiad:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE olympiad_result SET score=0, state=5 WHERE olympiad_id=%s", [olympiad_id])
            cursor.execute("UPDATE olympiad_result r \
                            SET score = p.max_score \
                            FROM olympiad_problem p \
                            WHERE r.problem_id = p.id \
                                AND r.answer = p.numerical_answer \
                                AND p.olympiad_id = %s", [olympiad_id])

        # olympiad.json_results = to_json(olympiad_id)
        # olympiad.save()
    else:
        return HttpResponse("Olympiad doesn't exist.")
    # return JsonResponse(olympiad.json_results, safe=False)
    return HttpResponse("Ok.")


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

def createCertificate(request, quiz_id, contestant_id):
    if quiz_id == 102:
        template = '1.png'
    elif quiz_id == 100:
        template = '2.png'
    elif quiz_id == 101:
        template = '3.png'
    elif quiz_id == 103:
        template = '4.png'
    elif quiz_id == 104:
        template = '5.png'
    else:
        return HttpResponse("quiz_id do not match")
    try:
        contestant = User.objects.get(pk=contestant_id)
        results = Result.objects.filter(olympiad_id=quiz_id, contestant_id=contestant_id)
        total = 0
        for result in results:
            total = total + int(result.score)
            # if total == 0:
            # return HttpResponse("Оролцоогүй эсвэл оноо аваагүй.")
    except:
        return HttpResponse("contestant or results")

    TEX_ROOT = "/home/deploy/django/latex"
    xelatex = '/usr/bin/xelatex'
    os.chdir(TEX_ROOT)
    name = '{}-{}'.format(quiz_id, contestant_id)
    context = {
        'lastname': contestant.last_name,
        'firstname': contestant.first_name,
        'points': total,
        'template': template,
    }
    content = render_template_with_context('certificate.tex', context)
    with io.open('{}.tex'.format(name), "w") as f:
        print(content, file=f)
    os.system('{} -synctex=1 -interaction=nonstopmode {}.tex'.format(xelatex, name))
    os.system('{} {}.tex'.format(xelatex, name))

    return FileResponse(open('{}.pdf'.format(name), 'rb'))
