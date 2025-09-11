# accounts/views/auth.py

from django.shortcuts import render, redirect, reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView

from ..forms import UserForm, UserMetaForm, LoginForm, CustomPasswordResetForm
from ..models import UserMeta

@login_required(login_url='/accounts/login/')
def profile(request):
    if request.POST:
        form1 = UserForm(request.POST, request.FILES, instance=request.user)
        form1.save()
        instance = UserMeta.objects.get(user_id=request.user.id)
        form2 = UserMetaForm(request.POST, instance=instance)
        form2.save()
        return redirect('user_profile_done')
    form1 = UserForm(instance=request.user)
    user_meta, created = UserMeta.objects.get_or_create(user_id=request.user.id)
    form2 = UserMetaForm(instance=user_meta)
    return render(request, 'accounts/register.html', {'form1': form1, 'form2': form2})

def profile_ready(request):
    return render(request, 'accounts/profile_ready.html')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = LoginForm(request.POST or None)
    if form.is_valid():
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)

            # (object, created) гэсэн зөв дарааллаар нь хувьсагчид оноох
            meta, created = UserMeta.objects.get_or_create(user=user)

            next_url = request.GET.get('next', '/')

            # Одоо 'meta' нь UserMeta объект тул энэ шалгалт зөв ажиллана
            if not meta.is_valid:
                next_url = reverse('user_profile')
            return redirect(next_url)
        else:
            request.session['invalid_user'] = 1
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return render(request, 'accounts/logout.html')

class CustomPasswordResetView(PasswordResetView):
    form_class = CustomPasswordResetForm
    email_template_name = 'registration/password_reset_email.html'
    success_url = '/password_reset/done/'