# emails/forms.py
from django import forms
from .models import EmailCampaign


class EmailCampaignForm(forms.ModelForm):
    """
    Email Campaign үүсгэх form
    """
    email_list = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 8,
            'placeholder': 'Имэйл хаягуудыг шинэ мөрөнд бичнэ үү:\nuser1@example.com\nuser2@example.com',
            'class': 'form-control'
        }),
        help_text='Custom имэйл жагсаалт сонгосон үед имэйл хаягуудыг оруулна',
        label='Имэйл жагсаалт'
    )

    class Meta:
        model = EmailCampaign
        fields = [
            'name',
            'subject',
            'from_email',  # --- ШИНЭЧЛЭЛ: Шинэ талбар нэмэгдсэн ---
            'message',
            'html_message',
            'filter_active_year',
            'filter_teachers',
            'filter_students',
            'filter_school_managers',
            'specific_province',
            'specific_school',
            'use_custom_list',
            'unique_per_email',
            'daily_limit'
        ]

        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Campaign нэр'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Имэйлийн гарчиг'}),
            'from_email': forms.Select(attrs={'class': 'form-select'}), # --- ШИНЭЧЛЭЛ: Dropdown болгосон ---
            'message': forms.Textarea(attrs={'rows': 10, 'class': 'form-control'}),
            'filter_active_year': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'filter_teachers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'filter_students': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'filter_school_managers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'specific_province': forms.Select(attrs={'id': 'province-select', 'class': 'form-select'}),
            'specific_school': forms.Select(attrs={'id': 'school-select', 'class': 'form-select'}),
            'use_custom_list': forms.CheckboxInput(attrs={'id': 'use-custom-list', 'class': 'form-check-input'}),
            'unique_per_email': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'daily_limit': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }

        labels = {
            'name': 'Campaign нэр',
            'subject': 'Имэйлийн гарчиг',
            'from_email': 'Илгээгч имэйл', # --- ШИНЭЧЛЭЛ: Талбарын нэр ---
            'message': 'Мессеж (Text)',
            'html_message': 'HTML мессеж (optional)',
            'filter_active_year': 'Сүүлийн жилд идэвхитэй',
            'filter_teachers': 'Багш нар',
            'filter_students': 'Сурагчид',
            'filter_school_managers': 'Сургуулийн менежер',
            'specific_province': 'Аймаг',
            'specific_school': 'Сургууль',
            'use_custom_list': 'Custom имэйл жагсаалт ашиглах',
            'unique_per_email': 'Нэг имэйл рүү 1 удаа илгээх',
            'daily_limit': 'Өдрийн лимит',
        }

        help_texts = {
            'from_email': 'Энэ campaign-г ямар имэйл хаягаас илгээхийг сонгоно уу.',
            'unique_per_email': 'Сонгосон бол нэг имэйл хаяг руу 1 л удаа илгээнэ. Сонгоогүй бол хэрэглэгч бүрт илгээнэ (ижил имэйлтэй хүмүүс бүгдэд очно).',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'specific_province' in self.fields:
            self.fields['specific_province'].required = False
            self.fields['specific_province'].empty_label = "--- Бүх аймаг ---"

        if 'specific_school' in self.fields:
            self.fields['specific_school'].required = False
            self.fields['specific_school'].queryset = self.fields['specific_school'].queryset.none()
            self.fields['specific_school'].empty_label = "--- Эхлээд аймаг сонгоно уу ---"

            if self.instance and self.instance.pk and self.instance.specific_province:
                try:
                    from schools.models import School
                    self.fields['specific_school'].queryset = School.objects.filter(province=self.instance.specific_province)
                except Exception:
                    pass
            elif 'specific_province' in self.data:
                try:
                    from schools.models import School
                    province_id = int(self.data.get('specific_province'))
                    self.fields['specific_school'].queryset = School.objects.filter(province_id=province_id)
                except (ValueError, TypeError):
                    pass

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('use_custom_list') and not cleaned_data.get('email_list', '').strip():
            raise forms.ValidationError('Custom имэйл жагсаалт сонгосон бол имэйл хаягууд оруулна уу!')
        return cleaned_data