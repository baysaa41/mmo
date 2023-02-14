from django.forms import ModelForm
from django.contrib.auth.models import User
from .models import UserMeta
from django import forms


class UserForm(ModelForm):
    class Meta:
        model = User
        fields = ['last_name', 'first_name', 'email']
        labels = {
            'last_name': 'Овог:',
            'first_name': 'Нэр:',
            'email': 'Цахим шуудан:'
        }


class UserMetaForm(ModelForm):
    class Meta:
        model = UserMeta
        fields = ['reg_num', 'province', 'school', 'grade', 'level', 'gender', 'mobile', 'is_valid']
        labels = {
            'reg_num': 'Регистрийн дугаар:',
            'province': 'Аймаг, дүүрэг (сургуулийн):',
            'school': 'Сургууль:',
            'grade': 'Анги:',
            'level': 'Ангилал',
            'gender': 'Хүйс:',
            'mobile': 'Холбогдох утас:',
            'is_valid': 'Ашиглах нөхцөлийг зөвшөөрөх'
        }


class LoginForm(forms.Form):
    username = forms.CharField(label='Хэрэглэгчийн нэр (Username):')
    password = forms.CharField(
        label='Нууц үг (Password):',
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'id': 'user-password'
            }
        )
    )

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

    def clean_username(self):
        username = self.cleaned_data.get('username')
        qs = User.objects.filter(username__iexact=username)
        if not qs.exists():
            raise forms.ValidationError("Ийм хэрэглэгч бүртгэгдээгүй байна.")
        return username
