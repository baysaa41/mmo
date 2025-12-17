# accounts/views/auth.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.contrib import messages
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator

from ..forms import UserForm, UserMetaForm, LoginForm, CustomPasswordResetForm, BulkAddUsersToSchoolForm
from ..models import UserMeta
import re

from oauth2_provider.decorators import protected_resource
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

@protected_resource(scopes=['profile'])
@require_http_methods(["GET"])
def user_info(request):
    """
    Access token ашиглан хэрэглэгчийн мэдээлэл буцаана
    """
    user = request.resource_owner  # OAuth токеноос хэрэглэгч авах

    return JsonResponse({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'phone': user.profile.phone if hasattr(user, 'profile') else None,
        'avatar': user.profile.avatar.url if hasattr(user, 'profile') and user.profile.avatar else None,
    })


@protected_resource(scopes=['profile'])
@require_http_methods(["GET"])
def user_full_profile(request):
    """
    Илүү дэлгэрэнгүй мэдээлэл
    """
    user = request.resource_owner

    return JsonResponse({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'date_joined': user.date_joined.isoformat(),
        'last_login': user.last_login.isoformat() if user.last_login else None,
        'is_active': user.is_active,
    })

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
        return redirect('posts:home')
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

@method_decorator(csrf_protect, name='dispatch')
class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """
    Нууц үг сэргээх баталгаажуулалтын view - CSRF алдаа засах
    """
    template_name = 'accounts/password_reset_confirm.html'
    success_url = '/accounts/password-reset-complete/'

    def dispatch(self, *args, **kwargs):
        """
        CSRF токен алдааг илүү сайн удирдах
        """
        return super().dispatch(*args, **kwargs)

@staff_member_required
def bulk_add_users_to_school_view(request):
    """
    Textarea-д оруулсан ID-тай хэрэглэгчдийг сонгосон сургуульд
    бөөнөөр нь нэмэх хуудас.
    """
    if request.method == 'POST':
        form = BulkAddUsersToSchoolForm(request.POST)
        if form.is_valid():
            school = form.cleaned_data['school']
            user_ids_raw = form.cleaned_data['user_ids']

            # Оруулсан текстийг задалж, тоон ID болгох
            # re.split ашиглан таслал, зай, шинэ мөрийг бүгдийг нь танина
            cleaned_ids = [int(uid) for uid in re.split(r'[\s,;]+', user_ids_raw) if uid.isdigit()]

            users_to_add = User.objects.filter(id__in=cleaned_ids)

            added_count = 0
            if school.group:
                for user in users_to_add:
                    # Хэрэглэгчийн сургууль тодорхойлогдоогүй бол тодорхойлох
                    if not user.data.school:
                        user.data.school = school
                        user.data.save()
                    # Хэрэглэгч аль хэдийн гишүүн биш бол нэмэх
                    if not user.groups.filter(pk=school.group.id).exists() and user.data.school.id == school.id:
                        school.group.user_set.add(user)
                        added_count += 1

            found_ids = users_to_add.values_list('id', flat=True)
            not_found_ids = set(cleaned_ids) - set(found_ids)

            messages.success(request, f"'{school.name}' сургуульд {added_count} шинэ сурагчийг амжилттай нэмлээ.")
            if not_found_ids:
                messages.warning(request, f"Дараах ID-тай хэрэглэгчид олдсонгүй: {', '.join(map(str, not_found_ids))}")

            return redirect('bulk_add_users_to_school')

    else:
        form = BulkAddUsersToSchoolForm()

    context = {
        'form': form,
    }
    return render(request, 'accounts/bulk_add_users.html', context)