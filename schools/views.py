from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, Q
from django.db import transaction
from django.core.mail import send_mail
import random
import string

from .models import School
from .forms import UserSearchForm, AddUserForm, UserForm, UserMetaForm
from accounts.models import UserMeta, Level
from olympiad.models import Olympiad

@login_required
def school_moderators_view(request):
    """
    Shows a list of schools. Staff users see all schools, while regular
    moderators only see their own.
    """
    if request.user.is_staff:
        schools_qs = School.objects.select_related('user__data', 'group', 'province')
    else:
        schools_qs = request.user.moderating.select_related('user__data', 'group', 'province')

    pid = request.GET.get('p')
    zid = request.GET.get('z')

    if pid:
        schools_qs = schools_qs.filter(province_id=pid)
    elif zid:
        schools_qs = schools_qs.filter(province__zone_id=zid)

    final_schools = schools_qs.order_by('province__name', 'name')
    olympiads = Olympiad.objects.filter(round=1, school_year=61)

    context = {
        'schools': final_schools,
        'olympiads': olympiads
    }
    return render(request, 'schools/school_moderators_list.html', context)

@login_required
def school_dashboard(request, school_id):
    """
    Displays the management dashboard for a single school.
    It shows a list of student categories and their counts.
    """
    school = get_object_or_404(School, id=school_id)
    if not request.user.is_staff and school not in request.user.moderating.all():
        messages.error(request, 'Та энэ сургуулийг удирдах эрхгүй.')
        return render(request, 'error.html', {'message': 'Хандах эрхгүй.'})

    student_counts = Level.objects.annotate(
        student_count=Count('usermeta__user', filter=Q(usermeta__user__groups=school.group))
    ).order_by('name')

    uncategorized_count = school.group.user_set.filter(data__level__isnull=True).count()

    context = {
        'school': school,
        'student_counts_by_level': student_counts,
        'uncategorized_count': uncategorized_count,
    }
    return render(request, 'schools/school_dashboard.html', context)

@login_required
def manage_school_by_level(request, school_id, level_id):
    """
    Сонгогдсон нэг ангиллын (эсвэл ангилалгүй) сурагчдыг удирдах хуудас.
    Энэ функц нь хайх, шинээр нэмэх, одоо байгааг нэмэх, хасах үйлдлүүдийг боловсруулна.
    """
    school = get_object_or_404(School, id=school_id)
    if not request.user.is_staff and school not in request.user.moderating.all():
        messages.error(request, 'Та энэ сургуулийг удирдах эрхгүй.')
        return render(request, 'error.html', {'message': 'Хандах эрхгүй.'})

    group = school.group

    # level_id == 0 байвал "Ангилалгүй" гэж үзнэ
    if level_id == 0:
        selected_level = {'id': 0, 'name': 'Ангилалгүй'}
        users_in_level = group.user_set.filter(data__level__isnull=True).select_related('data__grade')
    else:
        selected_level = get_object_or_404(Level, id=level_id)
        users_in_level = group.user_set.filter(data__level=selected_level).select_related('data__grade')

    search_results = None
    if request.method == 'POST':
        # Аль үйлдэл хийгдсэнээс хамаарч зөвхөн тухайн формыг боловсруулна
        if 'search_users' in request.POST:
            search_form = UserSearchForm(request.POST)
            add_user_form = AddUserForm() # Нөгөө формыг хоосон үлдээх
            if search_form.is_valid():
                search_results = search_form.search_users()

        elif 'add_user' in request.POST:
            add_user_form = AddUserForm(request.POST)
            search_form = UserSearchForm() # Нөгөө формыг хоосон үлдээх
            if add_user_form.is_valid():
                try:
                    with transaction.atomic():
                        new_user, password = add_user_form.save(commit=False)
                        new_user.username = ''.join(random.choice(string.ascii_letters) for _ in range(32))
                        new_user.save()
                        new_user.username = f'u{new_user.id}'
                        new_user.save()

                        # Шинэ хэрэглэгчийн UserMeta-г үүсгэх
                        meta_data = {
                            'user': new_user,
                            'school': request.user.data.school,
                            'province': request.user.data.province,
                        }
                        if level_id != 0:
                            meta_data['level'] = selected_level

                        UserMeta.objects.create(**meta_data)
                        new_user.groups.add(group)

                    try:
                        # TODO: Plaintext password илгээх нь аюулгүй байдлын эрсдэлтэй.
                        # Нууц үг сэргээх холбоос илгээдэг болгож сайжруулах хэрэгтэй.
                        subject = 'ММОХ - Шинэ бүртгэл'
                        message = f'Сайн байна уу, {new_user.first_name}.\n\nТаны хэрэглэгчийн нэр: {new_user.username}\nНууц үг: {password}'
                        send_mail(subject, message, 'baysa@mmo.mn', [new_user.email])
                        level_name = selected_level['name'] if level_id == 0 else selected_level.name
                        messages.success(request, f"'{new_user.get_full_name()}' хэрэглэгчийг '{level_name}' хэсэгт амжилттай нэмж, нэвтрэх мэдээллийг илгээлээ.")
                    except Exception as email_error:
                        messages.warning(request, f"Хэрэглэгч үүссэн ч и-мэйл илгээхэд алдаа гарлаа: {email_error}")

                except Exception as e:
                    messages.error(request, f"Хэрэглэгч үүсгэхэд алдаа гарлаа: {e}")

                return redirect('manage_school_by_level', school_id=school_id, level_id=level_id)

        elif 'add_existing_user' in request.POST:
            search_form = UserSearchForm()
            add_user_form = AddUserForm()
            user_id = request.POST.get('user_id')
            user_to_add = get_object_or_404(User, id=user_id)

            # --- ШИНЭЭР НЭМЭГДСЭН ШАЛГАЛТ ---
            # Хэрэглэгч өөр сургуулийн группт байгаа эсэхийг шалгах
            # Django-ийн админ (is_staff) болон тухайн сургуулийн группээс бусад группыг шалгана.
            existing_school_groups = user_to_add.groups.exclude(name=group.name).filter(school__isnull=False)

            if existing_school_groups.exists():
                other_school_name = existing_school_groups.first().school.name
                messages.error(request, f"'{user_to_add.get_full_name()}' хэрэглэгч '{other_school_name}' сургуульд аль хэдийн бүртгэлтэй байна.")
            else:
                group.user_set.add(user_to_add)
                messages.success(request, f"'{user_to_add.get_full_name() or user_to_add.username}' хэрэглэгчийг сургуульд амжилттай нэмлээ.")

            return redirect('manage_school_by_level', school_id=school_id, level_id=level_id)

        elif 'remove_user' in request.POST:
            search_form = UserSearchForm()
            add_user_form = AddUserForm()
            user_id = request.POST.get('user_id')
            user_to_remove = get_object_or_404(User, id=user_id)
            group.user_set.remove(user_to_remove)
            messages.info(request, f"'{user_to_remove.get_full_name() or user_to_remove.username}' хэрэглэгчийг сургуулиас хаслаа.")
            return redirect('manage_school_by_level', school_id=school_id, level_id=level_id)

        else:
            # Танигдаагүй POST хүсэлт ирвэл формуудыг хоосон харуулах
            search_form = UserSearchForm()
            add_user_form = AddUserForm()

    else:
        # GET хүсэлтийн үед бүх формыг хоосон үүсгэх
        search_form = UserSearchForm()
        add_user_form = AddUserForm()

    context = {
        'school': school,
        'group': group,
        'selected_level': selected_level,
        'users_in_level': users_in_level,
        'search_form': search_form,
        'add_user_form': add_user_form,
        'search_results': search_results,
    }
    return render(request, 'schools/manage_school.html', context)

@login_required
def edit_user_in_group(request, user_id):
    """
    Handles editing a student's profile information by a school moderator.
    Provides context for the "back" links in the template.
    """
    target_user = get_object_or_404(User, id=user_id)

    # --- ШИНЭЧИЛСЭН ЛОГИК ---
    if request.user.is_staff:
        # Хэрэв staff бол сурагчийн харьяалагддаг эхний сургуулийг олно
        school = School.objects.filter(group__user=target_user).first()
    else:
        # Хэрэв энгийн модератор бол өөрийн удирддаг сургууль мөн эсэхийг шалгана
        school = School.objects.filter(group__user=target_user, user=request.user).first()
        if not school:
            messages.error(request, 'Та энэ хэрэглэгчийг засах эрхгүй.')
            return render(request, 'error.html', {'message': 'Хандах эрхгүй.'})

    # Ensure the user has a UserMeta profile.
    user_meta = get_object_or_404(UserMeta, user=target_user)

    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=target_user)
        user_meta_form = UserMetaForm(request.POST, request.FILES, instance=user_meta)

        if user_form.is_valid() and user_meta_form.is_valid():
            user_form.save()
            user_meta_form.save()
            messages.success(request, 'Профайлыг амжилттай шинэчиллээ!')
            return redirect('edit_user_in_group', user_id=user_id)
        else:
            messages.error(request, 'Доорх алдааг засна уу.')
    else:
        user_form = UserForm(instance=target_user)
        user_meta_form = UserMetaForm(instance=user_meta)

    context = {
        'user_form': user_form,
        'user_meta_form': user_meta_form,
        'target_user': target_user,
        'school': school,
        'level': user_meta.level, # Pass the level for the back link
    }
    print(context['school'], context['level'])
    return render(request, 'schools/edit_user_in_group.html', context)

@login_required
def edit_profile(request):
    # This view is for users editing their own profile.
    # It doesn't need the back link logic.
    user = request.user
    user_meta, created = UserMeta.objects.get_or_create(user=user)

    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=user)
        user_meta_form = UserMetaForm(request.POST, request.FILES, instance=user_meta)
        if user_form.is_valid() and user_meta_form.is_valid():
            user_form.save()
            user_meta_form.save()
            messages.success(request, 'Таны мэдээлэл амжилттай шинэчлэгдлээ.')
            return redirect('edit_profile')
    else:
        user_form = UserForm(instance=user)
        user_meta_form = UserMetaForm(instance=user_meta)

    context = {
        'user_form': user_form,
        'user_meta_form': user_meta_form,
    }
    return render(request, 'schools/edit_profile.html', context)

