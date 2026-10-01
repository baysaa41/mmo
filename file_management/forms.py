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
            current_year = SchoolYear.get_current() or SchoolYear.objects.first()
            if current_year:
                self.fields['school_year'].initial = current_year


class TrainingMaterialForm(forms.ModelForm):
    class Meta:
        model = FileUpload
        fields = ['title', 'teachers', 'school_year', 'description', 'file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'EGMO бэлтгэл 2026'}),
            'teachers': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Б. Батбаясгалан, Т. Хулан'}),
            'school_year': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                                 'placeholder': 'Агуулга: граф, Эйлерийн зам, ...'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'description': 'Тайлбар',
            'file': 'Файл',
            'school_year': 'Хичээлийн жил',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = True
        if self.instance.pk:
            # Засах үед файл солих нь заавал биш
            self.fields['file'].required = False
        else:
            current_year = SchoolYear.get_current() or SchoolYear.objects.first()
            if current_year:
                self.fields['school_year'].initial = current_year

    def save(self, commit=True):
        self.instance.kind = FileUpload.Kind.TRAINING
        return super().save(commit=commit)
