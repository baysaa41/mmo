from django.forms import ModelForm
from django import forms
from .models import Result, Upload, ScoreSheet
from .widgets import MultiFileInput
from accounts.models import Province
from schools.models import School


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


# forms.py
class ChangeScoreSheetSchoolForm(forms.Form):
    province = forms.ModelChoiceField(
        queryset=Province.objects.all().order_by("name"),
        label="Аймаг/Дүүрэг",
        widget=forms.Select(attrs={"class": "form-select", "id": "province-select"})
    )
    school = forms.ModelChoiceField(
        queryset=School.objects.none(),
        label="Сургууль",
        widget=forms.Select(attrs={"class": "form-select", "id": "school-select"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # POST хийж байхад province сонгогдсон байвал сургуулиудыг filter хийнэ
        if "province" in self.data:
            try:
                province_id = int(self.data.get("province"))
                self.fields["school"].queryset = School.objects.filter(province_id=province_id).order_by("name")
            except (ValueError, TypeError):
                pass
        elif self.initial.get("province"):
            self.fields["school"].queryset = School.objects.filter(province=self.initial["province"]).order_by("name")
