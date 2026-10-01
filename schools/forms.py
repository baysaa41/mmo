from django import forms
from django.contrib.auth import get_user_model
User = get_user_model()
from django.db.models import Q
from accounts.models import UserMeta
from django.contrib.auth.forms import SetPasswordForm
from schools.models import School
from schools.models import UploadedExcel
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError
import re

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['last_name', 'first_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control','disabled': True}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Овог'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Нэр'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Имэйл'}),
        }
        help_texts = {
            'email': 'Итгэмжлэгдсэн имэйл хаяг.',
        }
        labels = {
            'last_name': 'Овог',
            'first_name': 'Нэр',
            'email': 'Имэйл',
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            validator = EmailValidator()
            try:
                validator(email)
            except ValidationError:
                raise forms.ValidationError('Зөв имэйл хаяг оруулна уу.')

        return email

# AddUserForm - Шинэ хэрэглэгч ҮҮСГЭХ зориулалттай
class AddUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['last_name', 'first_name', 'email']
        widgets = {
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Овог'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Нэр'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Имэйл'}),
        }
        labels = {
            'last_name': 'Овог',
            'first_name': 'Нэр',
            'email': 'Имэйл',
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise forms.ValidationError('И-мэйл хаяг заавал шаардлагатай.')

        validator = EmailValidator()
        try:
            validator(email)
        except ValidationError:
            raise forms.ValidationError('Зөв имэйл хаяг оруулна уу.')

        return email

class UserMetaForm(forms.ModelForm):
    class Meta:
        model = UserMeta
        fields = ['province', 'grade', 'level', 'gender', 'mobile', 'is_valid']
        widgets = {
            'mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Гар утас'}),
            'is_valid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'mobile': 'Гар утасны дугаар оруулна уу.',
        }
        labels = {
            'grade': 'Анги',
            'level': 'Ангилал',
            'gender': 'Хүйс',
            'mobile': 'Гар утас',
            'is_valid': 'Идэвхитэй эсэх',
        }


class InstitutionalAccountForm(forms.Form):
    """
    Байгууллагын албан аккаунт (сургуулийн удирдлага, аймаг/дүүргийн удирдах ажилтан) —
    хувь хүний биш. Нэр нь сургууль/аймгийн нэрээс тогтоогддог (schools.institutional);
    зөвхөн имэйл, гар утсыг тухайн үед хариуцаж буй хүнээр шинэчилнэ.
    """
    EMAIL_HELP = ''

    email = forms.EmailField(label='Имэйл', max_length=254,
                             widget=forms.EmailInput(attrs={'class': 'form-control'}))
    mobile = forms.RegexField(label='Гар утас', regex=r'^\d{8}$',
                              error_messages={'invalid': '8 оронтой утасны дугаар оруулна уу.'},
                              widget=forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric',
                                                            'maxlength': 8}))

    def __init__(self, *args, account, **kwargs):
        self.account = account
        meta = getattr(account, 'data', None)
        kwargs.setdefault('initial', {
            'email': account.email,
            'mobile': str(meta.mobile) if meta and meta.mobile else '',
        })
        super().__init__(*args, **kwargs)
        self.fields['email'].help_text = self.EMAIL_HELP

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def organization(self):
        """Мэдэгдэлд харуулах байгууллагын нэр ба аймаг (дэд классууд тодорхойлно)."""
        return self.account.get_full_name(), None

    def canonical_names(self):
        """Аккаунтын байх ёстой (first_name, last_name) (дэд классууд тодорхойлно)."""
        return self.account.first_name, self.account.last_name

    def save(self, changed_by=None):
        from schools.moderator import notify_account_email_changed
        account = self.account
        old_email = account.email
        account.first_name, account.last_name = self.canonical_names()
        account.email = self.cleaned_data['email']
        account.save(update_fields=['first_name', 'last_name', 'email'])
        meta, _ = UserMeta.objects.get_or_create(user=account)
        meta.mobile = int(self.cleaned_data['mobile'])
        meta.save(update_fields=['mobile'])
        organization, province = self.organization()
        notify_account_email_changed(account, old_email, changed_by, organization, province)
        return account


class SchoolManagerAccountForm(InstitutionalAccountForm):
    """Сургуулийн удирдлагын (менежер) албан аккаунт."""
    EMAIL_HELP = 'Сургуулийн удирдлагын өөрийн имэйл. Бүртгэгч багш солигдоход энэ хаяг руу мэдэгдэл очно.'

    role = forms.ChoiceField(label='Аккаунт эзэмшигч', widget=forms.Select(attrs={'class': 'form-select'}),
                             help_text='Аккаунтын нэр "{аймаг} {сургууль} — {сонголт}" хэлбэрээр харагдана.')

    def __init__(self, *args, school, **kwargs):
        from schools.institutional import SCHOOL_MANAGER_FIRST_NAME, SCHOOL_MANAGER_ROLES
        self.school = school
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = [(r, r) for r in SCHOOL_MANAGER_ROLES]
        current = self.account.first_name
        self.fields['role'].initial = current if current in SCHOOL_MANAGER_ROLES else SCHOOL_MANAGER_FIRST_NAME
        # Эзэмшигчийн сонголтыг эхэнд харуулна
        self.order_fields(['role', 'email', 'mobile'])

    def organization(self):
        return f'{self.school.name} ({self.school.province.name}) сургуулийн удирдлагын', self.school.province

    def canonical_names(self):
        from schools.institutional import school_manager_names
        return school_manager_names(self.school, role=self.cleaned_data.get('role'))

    def clean_email(self):
        from schools.moderator import norm_email
        email = super().clean_email()
        moderator = self.school.user if self.school else None
        if moderator and moderator.pk != self.account.pk and norm_email(moderator.email) == email:
            raise forms.ValidationError(
                'Бүртгэгч багшийн имэйлтэй ижил байж болохгүй. Сургуулийн удирдлагын өөрийн имэйлийг оруулна уу.')
        return email


class ProvinceAdminAccountForm(InstitutionalAccountForm):
    """Аймаг/дүүргийн удирдах ажилтны албан аккаунт (Province.contact_person, contact_person2)."""
    EMAIL_HELP = ('Аймаг/дүүргийн хариуцсан ажилтны имэйл. Сургуулиудын бүртгэлийн тайлан, '
                  'бүртгэгч багш солигдсон мэдэгдэл энэ хаяг руу очно.')

    def __init__(self, *args, province, **kwargs):
        self.province = province
        super().__init__(*args, **kwargs)

    def organization(self):
        return f'{self.province.name}-ийн удирдах ажилтны', self.province

    def canonical_names(self):
        from schools.institutional import province_contact_names
        return province_contact_names(self.province)


class ExcelUploadForm(forms.Form):
    file = forms.FileField()

# Form to search users
class UserSearchForm(forms.Form):
    query = forms.CharField(label='Хэрэглэгч хайх', max_length=100, required=False)

    def search_users(self):
        query = self.cleaned_data.get('query')
        if not query:
            return User.objects.none()

        # --- ID=... гэсэн хэлбэрийг шалгах хэсэг ---
        id_match = re.match(r'^id=(\d+)$', query.strip())
        if id_match:
            user_id = int(id_match.group(1))
            return User.objects.filter(id=user_id)

        filters = (
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(data__school__name__icontains=query) |
            Q(data__reg_num__icontains=query) |
            Q(data__mobile__icontains=query)
        )
        # Attempt to parse the query as an integer for the `id` field
        try:
            query_int = int(query)
            filters |= Q(id=query_int)
        except ValueError:
            pass  # If conversion fails, ignore the `id` filter

        return User.objects.filter(filters)


    def save(self, commit=True):
        user = super().save(commit=False)
        # Password ҮҮСГЭХГҮЙ - password reset link илгээнэ
        user.set_unusable_password()
        if commit:
            user.save()
        return user  # Password буцаахгүй болгох


class SchoolAdminPasswordChangeForm(SetPasswordForm):
    """
    Сургуулийн админд зориулсан нууц үг солих форм.
    Энэ нь SetPasswordForm-г өвлөж авсан тул нууц үгийн шалгалтыг автоматаар хийнэ.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control'})



class UploadExcelForm(forms.ModelForm):
    class Meta:
        model = UploadedExcel
        fields = ['file']
        labels = {
            'file': 'Дүнгийн Excel файл оруулах'
        }



class SchoolModeratorChangeForm(forms.Form):
    # Зөвхөн модератор байх боломжтой хэрэглэгчдийг шүүж харуулах нь зүйтэй.
    user = forms.ModelChoiceField(
        queryset=User.objects.order_by('last_name', 'first_name'),
        label="Шинэ модератор сонгох",
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class EditSchoolInfoForm(forms.ModelForm):
    class Meta:
        model = School
        fields = ['name', 'alias', 'province']
        labels = {
            'name': 'Сургуулийн нэр',
            'alias': 'Өөр нэрс',
            'province': 'Аймаг/Дүүрэг',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'alias': forms.Textarea(attrs={'class': 'form-control'}),
            'province': forms.Select(attrs={'class': 'form-select'}),
        }
