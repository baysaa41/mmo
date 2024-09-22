from django import forms
from .models import Result, QuizStatus, Upload, Problem, Quiz
from olympiad.widgets import MultiFileInput


class QuizStatusForm(forms.ModelForm):
    class Meta:
        model = QuizStatus
        fields = ['sisi']


class ResultsForm(forms.ModelForm):
    class Meta:
        model = Result
        fields = ('score','comment')
        labels = {
            'score': 'Оноо:',
            'comment': 'Тайлбар:'
        }


class UploadForm(forms.ModelForm):
    # file = forms.ImageField(widget=forms.ClearableFileInput(attrs={'multiple': True}),label='Бодолтын зураг:')
    file = forms.ImageField(widget=MultiFileInput(attrs={'multiple': True}), label='Бодолтын зураг:')
    class Meta:
        model = Upload
        fields = '__all__'
        widgets = {'result': forms.HiddenInput()}


class ProblemEditForm(forms.ModelForm):
    quiz = forms.ModelChoiceField(queryset=Quiz.objects.all().order_by('-id')[:5])
    class Meta:
        model = Problem
        fields = '__all__'