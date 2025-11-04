from django.shortcuts import render, reverse, get_object_or_404
from olympiad.models import Olympiad, Result
from django.contrib.auth.decorators import login_required
from django.forms import modelformset_factory
from .forms import ResultsForm, UploadForm


from schools.models import School

ResultsFormSet = modelformset_factory(Result, form=ResultsForm, extra=0)

@login_required()
def supplement_home(request):
    olympiads = Olympiad.objects.filter(is_grading=True)
    # olympiads = {}

    return render(request, 'olympiad/supplement_home.html', {'olympiads': olympiads})

def is_my_student(teacher_id,student_id):
    try:
        school = School.objects.get(user_id=teacher_id)
        if school.group.user_set.filter(id=student_id).exists():
            return True
    except:
        pass
    return False

def get_result_form(request):
    """
    AJAX request-аар UploadForm буцаах
    """
    result_id = request.GET.get('result_id')
    result = get_object_or_404(Result, pk=result_id)

    # Form үүсгэх
    form = UploadForm(initial={'result': result})

    # Form action URL үүсгэх
    olympiad_id = result.olympiad.id

    # StudentExamView эсвэл StudentSupplementView-н URL
    # Хэрэв exam бол 'student_exam', supplement бол 'student_supplement_view'
    is_supplement = request.GET.get('is_supplement', False)

    if is_supplement:
        form_action_url = reverse('student_supplement_view', kwargs={'olympiad_id': olympiad_id})
    else:
        form_action_url = reverse('student_exam', kwargs={'olympiad_id': olympiad_id})

    context = {
        'form': form,
        'result': result,
        'form_action_url': form_action_url,  # ← ЭНЭ ШИНЭ
    }

    return render(request, 'olympiad/upload_form.html', context)


@login_required
def student_exam_materials_view(request):
    user_id = request.GET.get('user_id', request.user.id)
    results = Result.objects.filter(contestant_id=user_id)
    title = "ID: {}, {}, {} сурагчийн илгээсэн материалууд".format(request.user.id, request.user.first_name,
                                                                   request.user.last_name)

    return render(request, 'olympiad/student_exam_materials_view.html', {'results': results, 'title': title})