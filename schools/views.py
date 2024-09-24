import openpyxl
from django.core.mail import send_mail
from django.contrib.auth.models import User, Group
from django.db.backends.dummy.base import ignore
from django.shortcuts import render, redirect, get_object_or_404
from accounts.models import UserMeta, Province  # Assuming you have UserMeta model
from .forms import ExcelUploadForm
from .models import School
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .forms import UserSearchForm, AddUserForm

import random
import string
import re

def clean_string(value):
    """ Remove surrogate characters from a string. """
    return re.sub(r'[\ud800-\udfff]', '', value)

def generate_password(length=8):
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for i in range(length))

def handle_excel_file(file):
    wb = openpyxl.load_workbook(file)
    sheet = wb.active  # First sheet

    # Start reading from the first row with data (e.g., row 2 if row 1 contains headers)
    for row in sheet.iter_rows(min_row=2, values_only=True):
        try:
            num, lastname, firstname, email, reg_num, gender, province_id, school, mobile = row
            lastname = re.sub(r'[\ud800-\udfff]', '', str(lastname))
            firstname = re.sub(r'[\ud800-\udfff]', '', str(firstname))
            email = re.sub(r'[\ud800-\udfff]', '', str(email))
            reg_num = re.sub(r'[\ud800-\udfff]', '', str(reg_num))
            gender = re.sub(r'[\ud800-\udfff]', '', str(gender))
            province_id = int(re.sub(r'[\ud800-\udfff]', '', str(province_id)))
            school = re.sub(r'[\ud800-\udfff]', '', str(school))
            mobile = re.sub(r'[\ud800-\udfff]', '', str(mobile))
        except Exception as e:
            print(e)

        # Create the user
        password = generate_password()
        try:
            user = User.objects.create_user(
                username='u'.join(random.choice(string.ascii_letters) for i in range(32)),  # Temp, will update later
                first_name=firstname,
                last_name=lastname,
                email=email,
                password=password
            )
            user.username = f'u{user.id}'  # Username like u+user.id
            user.save()
        except Exception as e:
            print(e)

        try:
            province = Province.objects.get(pk=province_id)
            # Create related UserMeta information
            user_meta = UserMeta.objects.create(
                user=user,
                reg_num=reg_num,
                province_id=province_id,
                school=school,
                grade_id=14,
                level_id=7,
                mobile=mobile,
                gender=gender[:2].upper(),
            )
        except Exception as e:
            print(e)

        try:

            # Assign to a group (optional, assuming group name is derived from the user somehow)
            group, created = Group.objects.get_or_create(name=f'{province.name}, {school}')
            # Assign user as the moderator of the group
            School.objects.get_or_create(user=user, group=group, province=province, name=school)
        except Exception as e:
            print(e)

        # Send an email with the credentials
            # Clean the values
            subject = clean_string('ММОХ, Таны бүртгэлийн мэдээлэл')
            message = clean_string(f'Таны хэрэглэгчийн нэр {user.username}, нууц үг {password}')
            sender_email = clean_string('baysa.edu@gmail.com')
            recipient_email = clean_string(user.email)

            # Send the email
            send_mail(
                subject,  # Cleaned subject
                message,  # Cleaned message
                sender_email,  # Cleaned sender email
                [recipient_email],  # Cleaned recipient email
                fail_silently=False,
            )
        except Exception as e:
            print(f'Имэйл алдаа: {e}')
            import traceback
            traceback.print_exc()

def user_creation_view(request):
    if request.method == 'POST':
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            handle_excel_file(request.FILES['file'])
            return render(request, 'schools/upload_success.html')
    else:
        form = ExcelUploadForm()

    return render(request, 'schools/upload.html', {'form': form})


def school_moderators_view(request):
    schools = School.objects.select_related('user', 'group', 'province').all()  # Fetch all schools and related data
    return render(request, 'schools/school_moderators_list.html', {'schools': schools})

from .forms import UserSearchForm, AddUserForm
from accounts.models import UserMeta  # Assuming UserMeta model for additional data

@login_required
def manage_school(request, school_id):
    school = get_object_or_404(School, id=school_id)
    group = school.group

    # List of users in the group
    users_in_group = group.user_set.all()

    # Initialize forms
    search_form = UserSearchForm()
    add_user_form = AddUserForm()
    search_results = None

    # Handle form submissions
    if request.method == 'POST':
        if 'search_users' in request.POST:
            # Search for users
            search_form = UserSearchForm(request.POST)
            if search_form.is_valid():
                query = search_form.cleaned_data.get('query')
                search_results = []

                if query.isdigit():
                    user_id = int(query)
                    try:
                        # Fetch the user with the provided ID
                        user_with_id = User.objects.get(id=user_id)
                        search_results.append(user_with_id)  # Add this user first
                    except ObjectDoesNotExist:
                        user_with_id = None  # User ID not found, set to None

                # Now search for other users based on the query
                other_results = User.objects.filter(
                    Q(username__icontains=query) |
                    Q(email__icontains=query) |
                    Q(first_name__icontains=query) |
                    Q(last_name__icontains=query) |
                    Q(data__reg_num__icontains=query) |
                    Q(data__mobile__icontains=query)
                ).exclude(id__in=[user.id for user in search_results if user])  # Exclude the user found by ID if it exists

                # Combine the results
                search_results.extend(other_results)
        elif 'add_existing_user' in request.POST:
            # Add an existing user to the group
            user_id = request.POST.get('user_id')
            user = User.objects.get(id=user_id)
            group.user_set.add(user)
            return redirect('manage_school', school_id=school.id)

        elif 'add_user' in request.POST:
            # Add a new user and assign them to the group
            add_user_form = AddUserForm(request.POST)
            if add_user_form.is_valid():
                new_user, password = add_user_form.save(commit=False)
                new_user.username = ''.join(random.choice(string.ascii_letters) for _ in range(32))
                new_user.save()
                try:
                    new_user.username = f'u{new_user.id}'
                    new_user.save()
                except Exception as e:
                    # Log the error for debugging, or take appropriate action
                    print(f"Error updating username: {e}")

                new_user.groups.add(group)  # Add new user to group

                # Optional: Send email with credentials
                send_mail(
                    'ММОХ бүртгэл',
                    f'Хэрэглэгчийн нэр: {new_user.username}\nНууц үг: {password}',
                    'baysa.edu@gmail.com',  # Your sender email
                    [new_user.email],
                    fail_silently=False,
                )

                return redirect('manage_school', school_id=school.id)

        elif 'remove_user' in request.POST:
            # Remove a user from the group
            user_id = request.POST.get('user_id')
            user = User.objects.get(id=user_id)
            group.user_set.remove(user)
            return redirect('manage_school', school_id=school.id)

    context = {
        'group': group,
        'users_in_group': users_in_group,
        'search_form': search_form,
        'add_user_form': add_user_form,
        'search_results': search_results,
    }

    return render(request, 'schools/manage_school.html', context)