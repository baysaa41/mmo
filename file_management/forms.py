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
        # Одоогийн жилийг анхдагч утга болгож сонгох, байхгүй бол сүүлийнх
        if self.instance.pk:
            # Засах үед файл солих нь заавал биш
            self.fields['file'].required = False
        else:
            self.fields['file'].required = True
            current_year = SchoolYear.get_current() or SchoolYear.objects.first()
            if current_year:
                self.fields['school_year'].initial = current_year


class TrainingMaterialForm(forms.ModelForm):
    class Meta:
        model = FileUpload
        fields = ['title', 'teachers', 'school_year', 'description', 'file', 'link']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'EGMO бэлтгэл 2026'}),
            'teachers': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Б. Батбаясгалан, Т. Хулан'}),
            'school_year': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                                 'placeholder': 'Агуулга: граф, Эйлерийн зам, ...'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://drive.google.com/...'}),
        }
        labels = {
            'description': 'Тайлбар',
            'file': 'Файл',
            'school_year': 'Хичээлийн жил',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = True
        if not self.instance.pk:
            current_year = SchoolYear.get_current() or SchoolYear.objects.first()
            if current_year:
                self.fields['school_year'].initial = current_year

    def clean(self):
        cleaned = super().clean()
        # Файл эсвэл холбоосын аль нэг нь заавал байх (засах үед хуучин файл тооцогдоно)
        has_file = bool(cleaned.get('file')) or (self.instance.pk and bool(self.instance.file))
        if not has_file and not cleaned.get('link'):
            raise forms.ValidationError('Файл оруулах эсвэл холбоос (Google Drive г.м.) оруулна уу.')
        return cleaned

    def save(self, commit=True):
        self.instance.kind = FileUpload.Kind.TRAINING
        return super().save(commit=commit)
