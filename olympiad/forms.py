from django.forms import ModelForm
from django import forms
from .models import Result, Upload
from .widgets import MultiFileInput


class ResultsForm(ModelForm):
    class Meta:
        model = Result
        fields = ('answer',)

    def __init__(self, *args, **kwargs):
        super(ResultsForm, self).__init__(*args, **kwargs)
        self.fields['answer'].label = 'Бодлого {}:'.format(self.instance.problem.order)


class ResultsGraderForm(ModelForm):
    class Meta:
        model = Result
        fields = ('score','grader_comment')
        labels = {
            'score': 'Оноо:',
            'grader_comment': 'Тайлбар'
        }


class UploadForm(ModelForm):
    file = forms.ImageField(widget=forms.ClearableFileInput(attrs={'multiple': True}),label='Бодолтын зураг:')
    # file = forms.ImageField(widget=MultiFileInput(attrs={'multiple': True}), label='Бодолтын зураг:')

    class Meta:
        model = Upload
        fields = ('result',)
        widgets = {
            'result': forms.HiddenInput()
        }

class UploadFileForm(forms.Form):
    file = forms.FileField()