# accounts/views/auth.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView
from django.contrib import messages
from django.contrib.auth.models import User

from ..forms import UserForm, UserMetaForm, LoginForm, CustomPasswordResetForm
from ..models import UserMeta

@login_required(login_url='/accounts/login/')
def profile(request):
    user_meta, created = UserMeta.objects.get_or_create(user_id=request.user.id)

    if request.method == 'POST':
        form1 = UserForm(request.POST, request.FILES, instance=request.user)
        form2 = UserMetaForm(request.POST, instance=user_meta)

        # <<< 2. Формууд зөв бөглөгдсөн эсэхийг шалгах
        if form1.is_valid() and form2.is_valid():
            form1.save()
            form2.save()
            # <<< 3. Амжилттай болсон тухай мэдээлэл нэмэх
            messages.success(request, 'Таны мэдээлэл амжилттай шинэчлэгдлээ.')
            return redirect('user_profile')
        else:
            # Хэрэв алдаатай бол алдааны мэдээллийг хэрэглэгчид харуулах
            messages.error(request, 'Мэдээллийг хадгалахад алдаа гарлаа. Талбаруудыг зөв бөглөнө үү.')

    else: # GET request үед
        form1 = UserForm(instance=request.user)
        form2 = UserMetaForm(instance=user_meta)

    return render(request, 'accounts/profile.html', {'user':request.user, 'form1': form1, 'form2': form2})

@staff_member_required
def user_profile_edit(request, user_id):
    user = User.objects.get(pk=user_id)
    user_meta, created = UserMeta.objects.get_or_create(user_id=user_id)

    if request.method == 'POST':
        form1 = UserForm(request.POST, request.FILES, instance=user)
        form2 = UserMetaForm(request.POST, instance=user_meta)

        # <<< 2. Формууд зөв бөглөгдсөн эсэхийг шалгах
        if form1.is_valid() and form2.is_valid():
            form1.save()
            form2.save()
            # <<< 3. Амжилттай болсон тухай мэдээлэл нэмэх
            messages.success(request, 'Хэрэглэгчийн мэдээлэл амжилттай шинэчлэгдлээ.')
            return redirect('user_profile_edit', user_id=user_id)
        else:
            # Хэрэв алдаатай бол алдааны мэдээллийг хэрэглэгчид харуулах
            messages.error(request, 'Мэдээллийг хадгалахад алдаа гарлаа. Талбаруудыг зөв бөглөнө үү.')

    else: # GET request үед
        form1 = UserForm(instance=user)
        form2 = UserMetaForm(instance=user_meta)

    return render(request, 'accounts/profile.html', {'user': user, 'form1': form1, 'form2': form2})

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