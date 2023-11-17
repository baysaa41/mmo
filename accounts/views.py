from django.shortcuts import render, redirect, HttpResponse
from accounts.forms import UserForm, UserMetaForm
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from .forms import LoginForm
from .models import UserMeta, Province, Level, Grade, UserMails, Zone
from django.urls import reverse
from django.core.mail import send_mass_mail
from olympiad.models import Article, SchoolYear, Result
from datetime import datetime, timezone

from django.db import connection
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from django.core.mail import get_connection, EmailMultiAlternatives

import os
import pandas as pd
import numpy as np
import string
import random
import re

# Create your views here.

def index(request):
    # shine hereglegchiin burtgel
    if request.user.is_authenticated:
        meta = UserMeta.objects.get_or_create(user=request.user)
        if not meta[0].is_valid:
            return redirect('user_profile')

    now = datetime.now(timezone.utc)
    mode = request.GET.get('mode', 0)

    school_year = SchoolYear.objects.filter(start__lt=now, end__gt=now).first()
    if school_year:
        id = request.GET.get('year', school_year.id)
        year = SchoolYear.objects.filter(pk=id).first()
    else:
        year = SchoolYear.objects.create()
        year.id = 0
        school_year = SchoolYear.objects.create()
        school_year.id = 0

    prev = SchoolYear.objects.filter(pk=year.id-1).first()
    next = SchoolYear.objects.filter(pk=year.id+1).first()

    articles = Article.objects.filter(year_id=year.id,IsShow=True).exclude(EndDate__lt=now).order_by('-IsSpec','-StartDate')

    context = {'articles': articles, 'mode': mode, 'year': year, 'prev': prev, 'next': next}

    return render(request, 'accounts/site_home.html', context=context)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = LoginForm(request.POST or None)
    if form.is_valid():
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')
        user = authenticate(request, username=username, password=password)
        if user != None:
            login(request, user)
            is_valid, meta = UserMeta.objects.get_or_create(user=user)
            if is_valid:
                next = request.GET.get('next', '/')
            else:
                next = reverse('user_profile')
            return redirect(next)
        else:
            request.session['invalid_user'] = 1
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return render(request, 'accounts/logout.html')


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
    user_meta = UserMeta.objects.get_or_create(user_id=request.user.id)
    form2 = UserMetaForm(instance=user_meta[0])
    return render(request, 'accounts/register.html', {'form1': form1, 'form2': form2})


def profile_ready(request):
    return render(request, 'accounts/profile_ready.html')

def users(request):
    #create_users()
    provinces = Province.objects.all()
    levels = Level.objects.all()
    p = request.GET.get('p', 0)
    l = request.GET.get('l', 0)
    if p == 0 and l == 0:
        return render(request, 'accounts/users-home.html', {'provinces': provinces, 'levels': levels})
    elif p != 0 and l != 0:
        users = UserMeta.objects.filter(province_id=int(p), level_id=int(l), is_valid=1).order_by('level_id')
        province = Province.objects.get(pk=p)
        level = Level.objects.get(pk=l)
        title = province.name + ', ' + level.name
        return render(request, 'accounts/users.html', {'users': users, 'title': title})
    elif p != 0:
        users = UserMeta.objects.filter(province_id=int(p), is_valid=1).order_by('level_id', 'grade_id')
        province = Province.objects.get(pk=p)
        return render(request, 'accounts/users.html', {'users': users, 'title': province.name})
    else:
        users = UserMeta.objects.filter(level_id=int(l), is_valid=1).order_by('grade_id', 'province_id')
        level = Level.objects.get(pk=l)
        return render(request, 'accounts/users.html', {'users': users, 'title': level.name})


def special_members(request):
    if request.user.is_staff:
        users = UserMeta.objects.filter(is_valid=1).filter(grade_id__gt=12).order_by('grade', 'province')
        return render(request, 'accounts/staff.html', {'users': users})
    else:
        return redirect('account_users')

def staff(request):
    users = User.objects.filter(is_staff=1).order_by('data__province__zone')
    return render(request, 'accounts/staff.html', {'users': users})


def group_users(request,group_id):
    group = Group.objects.filter(pk=group_id).first()
    title = group.name
    users = group.user_set.all().order_by('data__province__zone','data__province','data__school')

    z_id = request.GET.get('z',False)
    if z_id:
        zone = Zone.objects.filter(pk=z_id).first()
        title = group.name + ', ' + zone.name
        users = users.filter(data__province__zone_id=z_id)

    p_id = request.GET.get('p',False)
    if p_id:
        province = Province.objects.filter(pk=p_id).first()
        title = group.name + ', ' + province.name
        users = users.filter(data__province_id=p_id)

    g_id = request.GET.get('g',False)
    if g_id:
        grade = Grade.objects.filter(pk=g_id).first()
        title = title + ', ' + grade.name
        users = users.filter(data__grade_id=g_id)

    return render(request, 'accounts/users-group.html', {'group': group_id, 'users': users, 'title': title})

def get_active_emails():
    with connection.cursor() as cursor:
        cursor.execute("select distinct email from auth_user where is_active=1 and email<>''")
        emails = cursor.fetchall()

    return emails


def create_diploms_mail(request):
    num = 0
    subject = 'Охидын багыг дэмжих олммпиад батламж'
    from_email = 'ММОХ <no-reply@mmo.mn>'
    ids=[100,101,102,103,104]
    num = 0
    for id in ids:
        with connection.cursor() as cursor:
            cursor.execute("select distinct contestant_id from  olympiad_result where olympiad_id=%s", [id])
            results = cursor.fetchall()
            for result in results:
                contestant=User.objects.get(pk=result[0])
                text_html = render_to_string("newsletter/certificate_email.html", {'quiz_id': id, 'contestant_id': result[0]})
                text = strip_tags(text_html)
                UserMails.objects.create(subject=subject, text=text, text_html=text_html, from_email=from_email,
                                         to_email=contestant.email)
                num = num + 1
    return HttpResponse(num)

def create_emails(request):
    num = 0
    subject = 'ММОХ, Мэдээллийн товхимол №1'
    text_html = render_to_string("newsletter/202301.html")
    text = strip_tags(text_html)
    from_email = 'ММОХ <newsletter@mmo.mn>'

    emails = get_active_emails()
    for email in emails:
        UserMails.objects.create(subject=subject, text=text, text_html=text_html, from_email=from_email,
                                 to_email=email[0])
        num = num + 1
    return HttpResponse(num)

def create_mails(request):
    num = 0
    users = User.objects.all()
    subject = 'I шатны шалгаруулалт'
    text = '''
Та бүхэнд 2021-2022 оны хичээлийн жилийн мэндийг хүргэе!

2021-2022 оны хичээлийн жилээс эхлэн ММОХ I шатны сонгон шалгаруулалт хийхээр болж байна.

Шалгаруулалтын талаарх мэдээллийг www.mmo.mn сайтын мэдээллийн хэсгээс харж болно.

Шалгаруулалтад оролцохын тулд өөрийн бүртгэлийн мэдээллийг шинэчилсэн байх шаардлагатай.

Таны нэвтрэх нэр: {}

Хэрвээ та нууц үгээ мартсан бол нэвтрэх хуудасны Нууц үгээ сэргээх линк ашиглаарай.

Хэрвээ танд ямар нэг асуулт байвал baysa.edu@gmail.com хаягаар холбогдож асуугаарай 
(Ажлын ачааллаас шалтгаалж хариулт саатаж очихыг анхаарна уу!)

ММОХ
    '''
    from_email = 'Монголын Математикийн Олимпиадын Хороо <no-reply@mmo.mn>'

    for user in users:
        if user.is_active:
            UserMails.objects.create(subject=subject, text=text.format(user.username), from_email=from_email,
                                     to_email=user.email)
            num = num + 1
    return HttpResponse(num)


def send_user_mails(request):
    uemails = UserMails.objects.filter(is_sent=False)[0:50]
    emails = ()
    for email in uemails:
        new = (email.subject, email.text, email.from_email, [email.to_email])
        email.is_sent = True
        email.save()
        emails = (*emails, new)
    return HttpResponse(send_mass_mail(emails))


def send_mass_html_mail(request):
    """
    Given a datatuple of (subject, text_content, html_content, from_email,
    recipient_list), sends each message to each recipient list. Returns the
    number of emails sent.

    If from_email is None, the DEFAULT_FROM_EMAIL setting is used.
    If auth_user and auth_password are set, they're used to log in.
    If auth_user is None, the EMAIL_HOST_USER setting is used.
    If auth_password is None, the EMAIL_HOST_PASSWORD setting is used.

    """
    connection = get_connection(fail_silently=False)
    messages = []
    uemails = UserMails.objects.filter(is_sent=False)[0:50]
    for uemail in uemails:
        message = EmailMultiAlternatives(uemail.subject, uemail.text, uemail.from_email, [uemail.to_email])
        message.attach_alternative(uemail.text_html, 'text/html')
        messages.append(message)
        uemail.is_sent = True
        uemail.save()
    return HttpResponse(connection.send_messages(messages))

def create_users(request):
    imports = []

    count = 0
    for item in imports:
        user, created = User.objects.get_or_create(username=item[3])
        user.first_name=item[2]
        user.last_name=item[5]
        user.set_password(item[3])
        user.save()
        m, c = UserMeta.objects.get_or_create(user=user)
        m.is_valid = True
        m.save()
        if created:
            count = count + 1
    return HttpResponse(count)


def import_users():
    dir = '/home/deploy/2223'

    list = os.listdir(dir)
    print(list)
    num = 0
    for f in list:
        name = dir + '/' + f
        print(name)
        filename, file_extension = os.path.splitext(name)
        print(file_extension)
        if file_extension.lower() in ['.xls', '.xlsx']:
            try:
                df = pd.read_excel(name, 'Sheet1', engine='openpyxl')
                for item in df.iterrows():
                    ind, row = item
                    user, created = User.objects.get_or_create(username=row[row.keys()[3]])
                    if created:
                        user.firstname = row[row.keys()[2]]
                        user.set_password(row[row.keys()[3]])
                        user.save()
                        m, c = UserMeta.objects.get_or_create(user=user)
                        m.is_valid = True
                        m.save()
                        num = num + 1
            except:
                print('error')
                pass

    return num

def import_muis_students():
    dir = '/home/deploy/muis'

    list = os.listdir(dir)
    print(list)
    num = 0
    for f in list:
        name = dir + '/' + f
        print(name)
        filename, file_extension = os.path.splitext(name)
        print(file_extension)
        if file_extension.lower() in ['.xls', '.xlsx']:
            try:
                df = pd.read_excel(name, 'Sheet1', engine='openpyxl')
                for item in df.iterrows():
                    ind, row = item
                    user, created = User.objects.get_or_create(username=row[row.keys()[3]])
                    if created:
                        user.firstname = row[row.keys()[3]]
                        user.set_password(row[row.keys()[3]])
                        user.save()
                        m, c = UserMeta.objects.get_or_create(user=user)
                        m.is_valid = True
                        m.save()
                        num = num + 1
            except:
                print('error')
                pass

    return num

def random_string(n=8):
    characterList = string.ascii_letters + string.digits
    password = []
    for i in range(n):
        randomchar = random.choice(characterList)
        password.append(randomchar)
    return "".join(password)


# Define a function for
# for validating an Email
def check(email):
    regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    # pass the regular expression
    # and the string into the fullmatch() method
    if (re.fullmatch(regex, email)):
        return True
    else:
        return False

def create_mass_students():
    dir = '/home/deploy/registration'

    list = os.listdir(dir)
    print(list)
    num = 0
    for f in list:
        name = dir + '/' + f
        print(name)
        filename, file_extension = os.path.splitext(name)
        print(file_extension)
        if file_extension.lower() in ['.xls', '.xlsx']:
            df = pd.read_excel(name, 'contestants', engine='openpyxl')
            for item in df.iterrows():
                ind, row = item
                # print(item)
                # print(row['ID'])
                # print(row['Овог'])
                # print(row['Нэр'])
                # print(row['Утасны дугаар'])
                # print(row['Регистрийн дугаар'])
                # print(row['E-mail'])
                # print(row['Аймаг, Дүүргийн ID код'])
                # print(row['Сургууль'])
                # print(row['Анги'])
                # print(row['Оролцох ангилал'])
                # row['Анги']=10
                # print(row)
                levels = {
                    'B': 1,
                    'C': 2,
                    'D': 3,
                    'E': 4,
                    'F': 5,
                    'S': 6,
                    'T': 7,
                    'O': 8
                }
                salt = 'user' + random_string(8)
                try:
                    user = User.objects.get(pk=int(row['ID']))
                    created = False
                except:
                    if check(row['E-mail']):
                        email = row['E-mail']
                    else:
                        email = 'mmo60official@gmail.com'
                    user = User.objects.create_user(
                        username=salt,
                        first_name=row['Нэр'],
                        last_name=row['Овог'],
                        email=email
                    )
                    created = True
                    pass

                if created:
                    user.username = 'user' + str(user.id)
                    user.set_password(user.username)
                    try:
                        user.save()
                    except:
                        user.username = 'user' + str(user.id) + 's' + salt[-3:]
                        user.set_password(user.username)
                        user.save()
                    m, c = UserMeta.objects.get_or_create(user=user)
                    if c:
                        m.mobile = int(row['Утасны дугаар'])
                        m.grade_id = int(row['Анги'])
                        m.level_id = levels[row['Оролцох ангилал']]
                        m.province_id = int(row['Аймаг, Дүүргийн ID код'])
                        m.reg_num = row['Регистрийн дугаар']
                        m.is_valid = True
                        m.save()
                    num = num + 1

    return num
