# emails/forms.py
from django import forms
from .models import EmailCampaign


class EmailCampaignForm(forms.ModelForm):
    """
    Email Campaign үүсгэх form
    - Checkbox шүүлтүүртэй
    - Custom имэйл жагсаалттай
    - Province/School cascading dropdown
    """

    # Custom textarea field имэйл жагсаалтад
    email_list = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 8,
            'placeholder': 'Имэйл хаягуудыг шинэ мөрөнд бичнэ үү:\nuser1@example.com\nuser2@example.com\nuser3@example.com',
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
            'message',
            'html_message',
            'filter_active_year',
            'filter_teachers',
            'filter_students',
            'filter_school_managers',
            'specific_province',
            'specific_school',
            'use_custom_list',
            'daily_limit'
        ]

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Campaign нэр'
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Имэйлийн гарчиг'
            }),
            'message': forms.Textarea(attrs={
                'rows': 10,
                'class': 'form-control',
                'placeholder': 'Сайн байна уу {{name}},\n\nТаны мессеж энд...'
            }),
            'html_message': forms.Textarea(attrs={
                'rows': 10,
                'class': 'form-control',
                'placeholder': '<p>Сайн байна уу {{name}},</p><p>HTML мессеж...</p>'
            }),
            'filter_active_year': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'filter_teachers': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'filter_students': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'filter_school_managers': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'specific_province': forms.Select(attrs={
                'id': 'province-select',
                'class': 'form-control'
            }),
            'specific_school': forms.Select(attrs={
                'id': 'school-select',
                'class': 'form-control'
            }),
            'use_custom_list': forms.CheckboxInput(attrs={
                'id': 'use-custom-list',
                'class': 'form-check-input'
            }),
            'daily_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'value': 50000
            }),
        }

        labels = {
            'name': 'Campaign нэр',
            'subject': 'Имэйлийн гарчиг',
            'message': 'Мессеж (Text)',
            'html_message': 'HTML мессеж (optional)',
            'filter_active_year': 'Сүүлийн жилд идэвхитэй',
            'filter_teachers': 'Багш нар',
            'filter_students': 'Сурагчид',
            'filter_school_managers': 'Сургуулийн менежер',
            'specific_province': 'Аймаг',
            'specific_school': 'Сургууль',
            'use_custom_list': 'Custom имэйл жагсаалт ашиглах',
            'daily_limit': 'Өдрийн лимит',
        }

        help_texts = {
            'message': '{{name}} ашиглан хэрэглэгчийн нэрийг оруулна',
            'html_message': 'HTML формат (optional). {{name}} placeholder ашиглаж болно',
            'filter_active_year': 'Сүүлийн 1 жилд нэвтэрсэн хэрэглэгчид',
            'filter_teachers': 'Багш нар (level_id in [6, 7])',
            'filter_students': 'Сурагчид (level_id < 6)',
            'filter_school_managers': 'Сургуулийн менежерүүд (School.user)',
            'daily_limit': 'AWS SES өдрийн квот (default: 50,000)',
            'specific_province': 'Тодорхой аймгийн хэрэглэгчид (optional)',
            'specific_school': 'Аймаг сонгосны дараа сургууль харагдана (optional)',
            'use_custom_list': 'Checkbox-уудын оронд имэйл жагсаалт ашиглах',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Province select тохируулах
        if 'specific_province' in self.fields:
            self.fields['specific_province'].required = False
            self.fields['specific_province'].empty_label = "--- Бүх аймаг ---"

        # School select тохируулах
        if 'specific_school' in self.fields:
            self.fields['specific_school'].required = False
            self.fields['specific_school'].queryset = self.fields['specific_school'].queryset.none()
            self.fields['specific_school'].empty_label = "--- Эхлээд аймаг сонгоно уу ---"

            # Хэрэв province сонгогдсон бол харгалзах сургуулиудыг харуулах
            if self.instance and self.instance.pk and self.instance.specific_province:
                try:
                    from schools.models import School
                    self.fields['specific_school'].queryset = School.objects.filter(
                        province=self.instance.specific_province
                    )
                except Exception:
                    pass

            # POST request дээр province сонгогдсон бол
            elif 'specific_province' in self.data:
                try:
                    from schools.models import School
                    province_id = int(self.data.get('specific_province'))
                    self.fields['specific_school'].queryset = School.objects.filter(
                        province_id=province_id
                    )
                except (ValueError, TypeError):
                    pass

    def clean(self):
        """Form validation"""
        cleaned_data = super().clean()
        use_custom = cleaned_data.get('use_custom_list')
        email_list = cleaned_data.get('email_list', '').strip()

        # Custom list сонгосон бол имэйл жагсаалт шаардлагатай
        if use_custom and not email_list:
            raise forms.ValidationError(
                'Custom имэйл жагсаалт сонгосон бол имэйл хаягууд оруулна уу!'
            )

        # Custom list сонгоогүй бол ядаж нэг шүүлтүүр байх ёстой эсвэл province/school
        if not use_custom:
            has_filter = any([
                cleaned_data.get('filter_active_year'),
                cleaned_data.get('filter_teachers'),
                cleaned_data.get('filter_students'),
                cleaned_data.get('filter_school_managers'),
            ])

            has_location = any([
                cleaned_data.get('specific_province'),
                cleaned_data.get('specific_school'),
            ])

            # Хэрэв ямар ч шүүлтүүр байхгүй бол анхааруулга
            if not has_filter and not has_location:
                # Бүх хэрэглэгчдэд илгээх гэж байна гэсэн анхааруулга
                # Гэхдээ error биш, зөвшөөрнө
                pass

        return cleaned_data