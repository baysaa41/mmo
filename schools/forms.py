from django import forms
from django.contrib.auth.models import User, Group
from django.db.models import Q

class ExcelUploadForm(forms.Form):
    file = forms.FileField()

from django import forms
from django.contrib.auth.models import User

# Form to search users
class UserSearchForm(forms.Form):
    query = forms.CharField(label='Search Users', max_length=100, required=False)

    def search_users(self):
        query = self.cleaned_data.get('query')
        return User.objects.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(id__icontains=query) |
            Q(data__reg_num__icontains=query)
        )


# Form to add a new user
class AddUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def save(self, commit=True):
        user = super().save(commit=False)
        password = User.objects.make_random_password()  # Generate a random password
        user.set_password(password)
        if commit:
            user.save()
        return user, password  # Return both user and the generated password

