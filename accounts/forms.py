from django.forms import ModelForm
from django.contrib.auth.models import User, Group
from .models import UserMeta
from django import forms
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from olympiad.widgets import MultiFileInput
from django_select2.forms import ModelSelect2MultipleWidget

class AddRemoveUsersToGroupForm(forms.Form):
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=ModelSelect2MultipleWidget(
            model=User,
            search_fields=['username__icontains', 'email__icontains']
        ),
        label='Search and select users'
    )
    group = forms.ModelChoiceField(queryset=Group.objects.all(), label='Select a group')
    action = forms.ChoiceField(
        choices=[('add', 'Add to Group'), ('remove', 'Remove from Group')],
        widget=forms.RadioSelect,
        label='Action'
    )

class CustomPasswordResetForm(PasswordResetForm):
    email = forms.CharField(
        label="Хэрэглэгчийн нэр эсвэл имэйл хаяг",
        max_length=254,
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )
    def get_users(self, email):
        """
        Given an email, return matching user(s) who should receive a reset.
        """
        # We're overriding this method to use the username or email
        users = User.objects.filter(username=email, is_active=True) | User.objects.filter(email=email, is_active=True)
        return users

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        # print(subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name)
        """
        Send a django.core.mail.EmailMultiAlternatives to `to_email`.
        """
        subject = loader.render_to_string(subject_template_name, context)
        # Email subject *must not* contain newlines
        subject = "".join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        email_message = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, "text/html")

        email_message.send()
    def save(
        self,
        domain_override=None,
        subject_template_name="registration/password_reset_subject.txt",
        email_template_name="registration/password_reset_email.html",
        use_https=False,
        token_generator=default_token_generator,
        from_email=None,
        request=None,
        html_email_template_name=None,
        extra_email_context=None,
    ):
        """
        Generate a one-use only link for resetting password and send it to the
        user.
        """
        email = self.cleaned_data["email"]
        if not domain_override:
            current_site = get_current_site(request)
            site_name = current_site.name
            domain = current_site.domain
        else:
            site_name = domain = domain_override
        for user in self.get_users(email):
            user_email = user.email
            user_name = user.username
            context = {
                "email": user_email,
                "domain": domain,
                "site_name": site_name,
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "user": user,
                "user_name": user_name,
                "token": token_generator.make_token(user),
                "protocol": "https" if use_https else "http",
                **(extra_email_context or {}),
            }
            self.send_mail(
                subject_template_name,
                email_template_name,
                context,
                from_email,
                user_email,
                html_email_template_name=html_email_template_name,
            )
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

class EmailForm(forms.Form):
    subject = forms.CharField(max_length=100)
    message = forms.CharField(widget=forms.Textarea)
    attachments = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}), required=False)
