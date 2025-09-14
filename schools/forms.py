from django import forms
from django.contrib.auth import get_user_model
User = get_user_model()
from django.db.models import Q
from accounts.models import UserMeta

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['last_name', 'first_name', 'email']
        widgets = {
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Овог'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Нэр'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Имэйл'}),
        }
        help_texts = {
            'email': 'Итгэмжлэгдсэн имэйл хаягаа оруулна уу.',
        }
        labels = {
            'last_name': 'Овог',
            'first_name': 'Нэр',
            'email': 'Имэйл',
        }

class UserMetaForm(forms.ModelForm):
    class Meta:
        model = UserMeta
        fields = ['photo', 'province', 'grade', 'level', 'gender', 'mobile', 'is_valid']
        widgets = {
            # 'reg_num': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Регистрийн дугаар'}),
            'province': forms.Select(attrs={'class': 'form-control'}),
            # 'school': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Сургууль'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Гар утас'}),
            'is_valid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            # 'reg_num': 'Регистрийн дугаараа оруулна уу.',
            'mobile': 'Гар утасны дугаар оруулна уу.',
        }
        labels = {
            'photo': 'Зураг',
             # 'reg_num': 'Регистрийн дугаар',
            'province': 'Аймаг',
            # 'school': 'Сургууль',
            'grade': 'Анги',
            'level': 'Ангилал',
            'gender': 'Хүйс',
            'mobile': 'Гар утас',
            'is_valid': 'Идэвхитэй эсэх',
        }


class ExcelUploadForm(forms.Form):
    file = forms.FileField()

# Form to search users
class UserSearchForm(forms.Form):
    query = forms.CharField(label='Хэрэглэгч хайх', max_length=100, required=False)

    def search_users(self):
        query = self.cleaned_data.get('query')
        if not query:
            return User.objects.none()

        filters = (
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(data__school__icontains=query) |
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


# Form to add a new user
class AddUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['last_name', 'first_name', 'email']

    def save(self, commit=True):
        user = super().save(commit=False)
        password = User.objects.make_random_password()  # Generate a random password
        user.set_password(password)
        if commit:
            user.save()
        return user, password  # Return both user and the generated password

