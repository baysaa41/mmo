from django import forms
from accounts.models import Province, Zone


class ProvinceEditForm(forms.ModelForm):
    """Аймаг, дүүргийн мэдээлэл засварлах форм"""
    class Meta:
        model = Province
        fields = ['name', 'zone', 'contact_person']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'zone': forms.Select(attrs={'class': 'form-control'}),
            'contact_person': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': 'Аймаг, дүүргийн нэр',
            'zone': 'Бүс',
            'contact_person': 'Холбоо барих хүн',
        }


class ThresholdScoreForm(forms.Form):
    """Онооны босго тогтоох форм"""
    threshold_score = forms.FloatField(
        label='Босго оноо',
        min_value=0,
        max_value=100,
        help_text='Энэ оноо ба түүнээс дээш оноо авсан сурагчдыг нэмнэ',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.0',
            'step': '0.5'
        })
    )


class UploadExcelForm(forms.Form):
    """Excel файл оруулах форм"""
    excel_file = forms.FileField(
        label='Excel файл сонгох',
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
