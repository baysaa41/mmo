from django.shortcuts import render
from .forms import ProblemEditForm
from .models import Problem, Quiz, AnswerChoice, Result, Upload
from django.contrib.auth.decorators import login_required
from django.forms import inlineformset_factory

BookFormSet = inlineformset_factory(Problem, AnswerChoice, fields='__all__')

@login_required
def edit_problem(request):
    if request.method == 'POST':
        form = ProblemEditForm(request.POST)
        if form.is_valid():
            form.save()
        return render(request, 'quiz/problem_edit_form.html', {'form': form})

    problem_id = int(request.GET.get('problem_id',0))

    if Problem.objects.filter(pk=problem_id).exists():
        problem = Problem.objects.get(pk=problem_id)
        form = ProblemEditForm(instance=problem)
    else:
        form = ProblemEditForm()

    return render(request, 'quiz/problem_edit_form.html', {'form': form})