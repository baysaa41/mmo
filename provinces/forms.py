from django import forms


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
