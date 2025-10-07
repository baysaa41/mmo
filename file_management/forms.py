from django import forms
from .models import FileUpload
from olympiad.models import SchoolYear


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = FileUpload
        fields = ['description', 'file', 'school_year']
        widgets = {
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Файлын тайлбар оруулна уу...'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control'
            }),
            'school_year': forms.Select(attrs={
                'class': 'form-control'
            })
        }
        labels = {
            'description': 'Тайлбар',
            'file': 'Файл',
            'school_year': 'Хичээлийн жил'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Сүүлийн жилийг анхдагч утга болгож сонгох
        latest_year = SchoolYear.objects.first()  # ordering = ['-name']
        if latest_year:
            self.fields['school_year'].initial = latest_year