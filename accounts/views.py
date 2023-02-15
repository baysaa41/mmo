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
    usernames = ['20B1NUM2637',
                 '20B1NUM2295',
                 '17B1NUM1641',
                 '18B1NUM2022',
                 '20B1NUM0214',
                 '20B1NUM0666',
                 '20B1NUM0415',
                 '17B1NUM1200',
                 '20B1NUM1816',
                 '20B1NUM2095',
                 '20B1NUM0093',
                 '20B1NUM0441',
                 '20B1NUM1422',
                 '20B1NUM2376',
                 '20B1NUM1968',
                 '16B1SAS3244',
                 '20B1NUM2325',
                 '19B1NUM0735',
                 '20B1NUM1699',
                 '18B1NUM1049',
                 '20B1NUM2391',
                 '16B1SAS3828',
                 '18B1NUM1104',
                 '20B1NUM2118',
                 '20B1NUM0106',
                 '20B1NUM1720',
                 '19B1NUM0445',
                 '16B1SEAS1365',
                 '17B1NUM2799',
                 '20B1NUM0518',
                 '20B1NUM2124',
                 '19B1NUM0524',
                 '19B1NUM2123',
                 '20B1NUM0004',
                 '20B1NUM1819',
                 '20B1NUM1189',
                 '20B1NUM0384',
                 '20B1NUM0223',
                 '20B1NUM0121',
                 '20B1NUM0230',
                 '20B1NUM1351',
                 '20B1NUM0882',
                 '18B1NUM0462',
                 '20B1NUM2314',
                 '18B1NUM1076',
                 '20B1NUM1582',
                 '20B1NUM2277',
                 '20B1NUM0337',
                 '19B1NUM0801',
                 '19B1NUM1296',
                 '20B1NUM2566',
                 '20B1NUM2956',
                 '20B1NUM0116',
                 '20B1NUM0364',
                 '19B1NUM0297',
                 '20B1NUM0660',
                 '20B1NUM2079',
                 '19B1NUM1674',
                 '20B1NUM0225',
                 '20B1NUM1251',
                 '20B1NUM1698',
                 '18B1NUM0652',
                 '20B1NUM1781',
                 '17B1NUM2417',
                 '20B1NUM2114',
                 '20B1NUM2162',
                 '20B1NUM1071',
                 '20B1NUM0175',
                 '20B1NUM0115',
                 '20B1NUM2262',
                 '20B1NUM2053',
                 '20B1NUM1197',
                 '20B1NUM2075',
                 '20B1NUM2557',
                 '18B1NUM0786',
                 '20B1NUM0444',
                 '20B1NUM1970',
                 '19B1NUM1905',
                 '20B1NUM0279',
                 '20B1NUM0490',
                 '18B1NUM3460',
                 '20B1NUM0243']

    imports = [
        ['1', 'Био - инженерчлэл', 'Эрдэнэтуяа.Жар', '16B1SEAS1302', '16B1SEAS1302@stud.num.edu.mn', '96521228'],
        ['2', 'Компьютерийн ухаан', 'Ариунжаргал.Бат', '19B1NUM0728', '19B1NUM0728@stud.num.edu.mn', '88307797'],
         ['3', 'Компьютерийн ухаан', 'Бадрангийх.Бат', '20B1NUM2182', '20B1NUM2182@stud.num.edu.mn', '86682464'],
         ['4', 'Компьютерийн ухаан', 'Банзрагч.Сон', '20B1NUM2367', '20B1NUM2367@stud.num.edu.mn', '95443330'],
         ['5', 'Компьютерийн ухаан', 'Бат-Эрдэнэ.Бат', '18B1NUM1691', '18B1NUM1691@stud.num.edu.mn', '94096408'],
         ['6', 'Компьютерийн ухаан', 'Бат-Эрдэнэ.Бат', '19B1NUM1536', '19B1NUM1536@stud.num.edu.mn', '80017873'],
         ['7', 'Компьютерийн ухаан', 'Бат-Эрдэнэ.Эрд', '20B1NUM1641', '20B1NUM1641@stud.num.edu.mn', '95686131'],
         ['8', 'Компьютерийн ухаан', 'Билгүүн.Бат', '18B1NUM0243', '18B1NUM0243@stud.num.edu.mn', '90212700'],
         ['9', 'Компьютерийн ухаан', 'Билгүүн.Бар', '20B1NUM1083', '20B1NUM1083@stud.num.edu.mn', '99859899'],
         ['10', 'Компьютерийн ухаан', 'Буян-Урт.Хуя', '20B1NUM2570', '20B1NUM2570@stud.num.edu.mn', '99243596'],
         ['11', 'Компьютерийн ухаан', 'Буян-Учрал.Ама', '20B1NUM0082', '20B1NUM0082@stud.num.edu.mn', '80007554'],
         ['12', 'Компьютерийн ухаан', 'Бямбасүрэн.Лха', '18B1NUM2698', '18B1NUM2698@stud.num.edu.mn', '99611693'],
         ['13', 'Компьютерийн ухаан', 'Гал.Зор', '20B1NUM1766', '20B1NUM1766@stud.num.edu.mn', '85951056'],
         ['14', 'Компьютерийн ухаан', 'Ганбаяр.Бат', '18B1NUM2538', '18B1NUM2538@stud.num.edu.mn', '80182165'],
         ['15', 'Компьютерийн ухаан', 'Гандуулга.Ган', '20B1NUM1780', '20B1NUM1780@stud.num.edu.mn', '99856012'],
         ['16', 'Компьютерийн ухаан', 'Давааням.Дор', '20B1NUM1789', '20B1NUM1789@stud.num.edu.mn', '88433595'],
         ['17', 'Компьютерийн ухаан', 'Давгаренчин.Бая', '19B1NUM0177', '19B1NUM0177@stud.num.edu.mn', '99939755'],
         ['18', 'Компьютерийн ухаан', 'Золжаргал.Бат', '19B1NUM1102', '19B1NUM1102@stud.num.edu.mn', '80950501'],
         ['19', 'Компьютерийн ухаан', 'Зуунбилэг.Бат', '18B1NUM1220', '18B1NUM1220@stud.num.edu.mn', '89007861'],
         ['20', 'Компьютерийн ухаан', 'Минжинсор.Мяг', '20B1NUM2637', '20B1NUM2637@stud.num.edu.mn', '80255466'],
         ['21', 'Компьютерийн ухаан', 'Мөнхдэлгэр.Тул', '20B1NUM2295', '20B1NUM2295@stud.num.edu.mn', '88227559'],
         ['22', 'Компьютерийн ухаан', 'Мөнхнаран.Бая', '17B1NUM1641', '17B1NUM1641@stud.num.edu.mn', '85557667'],
         ['23', 'Компьютерийн ухаан', 'Мөнх-Оргил.Бат', '18B1NUM2022', '18B1NUM2022@stud.num.edu.mn', '94593727'],
         ['24', 'Компьютерийн ухаан', 'Мөнхцэцэг.Хад', '20B1NUM0214', '20B1NUM0214@stud.num.edu.mn', '99971357'],
         ['25', 'Компьютерийн ухаан', 'Мөнх-Эрдэнэ.Ерө', '20B1NUM0666', '20B1NUM0666@stud.num.edu.mn', '86668525'],
         ['26', 'Компьютерийн ухаан', 'Наран.Бат', '20B1NUM0415', '20B1NUM0415@stud.num.edu.mn', '99131313'],
         ['27', 'Компьютерийн ухаан', 'Номин.Ула', '20B1NUM2086', '20B1NUM2086@stud.num.edu.mn', '94481545'],
         ['28', 'Компьютерийн ухаан', 'Нурбек.Жал', '17B1NUM1200', '17B1NUM1200@stud.num.edu.mn', '99418795'],
         ['29', 'Компьютерийн ухаан', 'Оргилмаа.Бая', '20B1NUM1816', '20B1NUM1816@stud.num.edu.mn', '85240805'],
         ['30', 'Компьютерийн ухаан', 'Саруул.Ган', '20B1NUM2095', '20B1NUM2095@stud.num.edu.mn', '90330000'],
         ['31', 'Компьютерийн ухаан', 'Сүхбат.Алт', '20B1NUM0093', '20B1NUM0093@stud.num.edu.mn', '88187245'],
         ['32', 'Компьютерийн ухаан', 'Тамир.Рэн', '20B1NUM0441', '20B1NUM0441@stud.num.edu.mn', '95660626'],
         ['33', 'Компьютерийн ухаан', 'Төгөлдөр.Энх', '20B1NUM1422', '20B1NUM1422@stud.num.edu.mn', '99180501'],
         ['34', 'Компьютерийн ухаан', 'Тэгшжаргал.Отг', '20B1NUM2376', '20B1NUM2376@stud.num.edu.mn', '86709696'],
         ['35', 'Компьютерийн ухаан', 'Тэмүүжин.Дэл', '20B1NUM1968', '20B1NUM1968@stud.num.edu.mn', '95342424'],
         ['36', 'Компьютерийн ухаан', 'Хишигдэлгэр.Ган', '16B1SAS3244', '16B1SAS3244@stud.num.edu.mn', '80600613'],
         ['37', 'Компьютерийн ухаан', 'Хосбилэгт.Бил', '20B1NUM2325', '20B1NUM2325@stud.num.edu.mn', '85830880'],
         ['38', 'Компьютерийн ухаан', 'Хуншагай.Маш', '19B1NUM0735', '19B1NUM0735@stud.num.edu.mn', '99213661'],
         ['39', 'Компьютерийн ухаан', 'Цэцүүхэй.Дэл', '20B1NUM1699', '20B1NUM1699@stud.num.edu.mn', '95001112'],
         ['40', 'Компьютерийн ухаан', 'Чингүн.Унд', '18B1NUM1049', '18B1NUM1049@stud.num.edu.mn', '88811988'],
         ['41', 'Компьютерийн ухаан', 'Эйжи.Ган', '20B1NUM2391', '20B1NUM2391@stud.num.edu.mn', '99703133'],
         ['42', 'Компьютерийн ухаан', 'Энхбат.Бат', '16B1SAS3828', '16B1SAS3828@stud.num.edu.mn', '99295265'],
         ['43', 'Компьютерийн ухаан', 'Энхбат.Ама', '18B1NUM1104', '18B1NUM1104@stud.num.edu.mn', '95759901'],
         ['44', 'Компьютерийн ухаан', 'Энхмөнх.Ням', '20B1NUM2118', '20B1NUM2118@stud.num.edu.mn', '90951015'],
         ['45', 'Компьютерийн ухаан', 'Эрмүүн.Эрд', '20B1NUM0106', '20B1NUM0106@stud.num.edu.mn', '95973650'],
         ['46', 'Математик', 'Хунтуяа.Тог', '20B1NUM1720', '20B1NUM1720@stud.num.edu.mn', '88303767'],
         ['47', 'Мэдээллийн систем', 'Билгүүн.Лха', '19B1NUM0445', '19B1NUM0445@stud.num.edu.mn', '94034485'],
         ['48', 'Мэдээллийн систем', 'Намжилмаа.Дар', '16B1SEAS1365', '16B1SEAS1365@stud.num.edu.mn', '94248492'],
         ['49', 'Мэдээллийн систем', 'Тэмүүжин.Чул', '17B1NUM2799', '17B1NUM2799@stud.num.edu.mn', '88121278'],
         ['50', 'Мэдээллийн систем', 'Эрдэмбилэг.Түм', '20B1NUM0518', '20B1NUM0518@stud.num.edu.mn', '86667376'],
         ['51', 'Мэдээллийн технологи', 'Анужин.Дор', '20B1NUM2124', '20B1NUM2124@stud.num.edu.mn', '94288008'],
         ['52', 'Мэдээллийн технологи', 'Мичидмаа.Лув', '19B1NUM0524', '19B1NUM0524@stud.num.edu.mn', '99287956'],
         ['53', 'Мэдээллийн технологи', 'Тэмүүгэн.Ган', '19B1NUM2123', '19B1NUM2123@stud.num.edu.mn', '80209900'],
         ['54', 'Програм хангамж', 'Батхолбоо.Бат', '20B1NUM0004', '20B1NUM0004@stud.num.edu.mn', '99465786'],
         ['55', 'Програм хангамж', 'Ирмүүн.Түд', '20B1NUM1819', '20B1NUM1819@stud.num.edu.mn', '86452882'],
         ['56', 'Програм хангамж', 'Лувсням.Тэг', '20B1NUM1189', '20B1NUM1189@stud.num.edu.mn', '95374520'],
         ['57', 'Програм хангамж', 'Мичидмаа.Пүр', '20B1NUM0384', '20B1NUM0384@stud.num.edu.mn', '90138808'],
         ['58', 'Програм хангамж', 'Номин-Эрдэнэ.Ари', '20B1NUM0223', '20B1NUM0223@stud.num.edu.mn', '94756776'],
         ['59', 'Програм хангамж', 'Одонжаргал.Баа', '20B1NUM0121', '20B1NUM0121@stud.num.edu.mn', '99699066'],
         ['60', 'Програм хангамж', 'Сарнай.Түм', '20B1NUM0230', '20B1NUM0230@stud.num.edu.mn', '99319491'],
         ['61', 'Програм хангамж', 'Сарнай.Бор', '20B1NUM1351', '20B1NUM1351@stud.num.edu.mn', '90980998'],
         ['62', 'Програм хангамж', 'Султанбек.Жан', '20B1NUM0882', '20B1NUM0882@stud.num.edu.mn', '94228989'],
         ['63', 'Програм хангамж', 'Хантулга.Рад', '18B1NUM0462', '18B1NUM0462@stud.num.edu.mn', '95283737'],
         ['64', 'Програм хангамж', 'Цэнгүүн.Отг', '20B1NUM2314', '20B1NUM2314@stud.num.edu.mn', '80170737'],
         ['65', 'Програм хангамж', 'Энхжин.Гом', '18B1NUM1076', '18B1NUM1076@stud.num.edu.mn', '89899598'],
         ['66', 'Програм хангамж', 'Энхмандал.Бат', '20B1NUM1582', '20B1NUM1582@stud.num.edu.mn', '88469991'],
         ['67', 'Статистик', 'Ануужин.Алт', '20B1NUM2277', '20B1NUM2277@stud.num.edu.mn', '95434706'],
         ['68', 'Статистик', 'Баасандаш.Бат', '20B1NUM0337', '20B1NUM0337@stud.num.edu.mn', '95714129'],
         ['69', 'Статистик', 'Батгэрэл.Лув', '19B1NUM0801', '19B1NUM0801@stud.num.edu.mn', '95548446'],
         ['70', 'Статистик', 'Болортуул.Пүр', '19B1NUM1296', '19B1NUM1296@stud.num.edu.mn', '98888003'],
         ['71', 'Статистик', 'Будхүү.Нэр', '20B1NUM2566', '20B1NUM2566@stud.num.edu.mn', '99305728'],
         ['72', 'Статистик', 'Бямбадорж.Үүр', '20B1NUM2956', '20B1NUM2956@stud.num.edu.mn', '88262712'],
         ['73', 'Статистик', 'Бямбацэцэг.Баа', '20B1NUM0116', '20B1NUM0116@stud.num.edu.mn', '99322039'],
         ['74', 'Статистик', 'Дагвадорж.Ням', '20B1NUM0364', '20B1NUM0364@stud.num.edu.mn', '99929533'],
         ['75', 'Статистик', 'Мичидмаа.Сүх', '19B1NUM0297', '19B1NUM0297@stud.num.edu.mn', '89867005'],
         ['76', 'Статистик', 'Мөнхжаргал.Оюу', '20B1NUM0660', '20B1NUM0660@stud.num.edu.mn', '98387009'],
         ['77', 'Статистик', 'Намуун.Дав', '20B1NUM2079', '20B1NUM2079@stud.num.edu.mn', '80820286'],
         ['78', 'Статистик', 'Оролмаа.Мөн', '19B1NUM1674', '19B1NUM1674@stud.num.edu.mn', '98607544'],
         ['79', 'Статистик', 'Отгонцэцэг.Бая', '20B1NUM0225', '20B1NUM0225@stud.num.edu.mn', '89800217'],
         ['80', 'Статистик', 'Цэндсүрэн.Алт', '20B1NUM1251', '20B1NUM1251@stud.num.edu.mn', '80278897'],
         ['81', 'Статистик', 'Цэцэгсүрэн.Төм', '20B1NUM1698', '20B1NUM1698@stud.num.edu.mn', '94183736'],
         ['82', 'Статистик', 'Чимиддулам.Эрх', '18B1NUM0652', '18B1NUM0652@stud.num.edu.mn', '89767282'],
         ['83', 'Статистик', 'Эрдэнэсүрэн.Бол', '20B1NUM1781', '20B1NUM1781@stud.num.edu.mn', '95898629'],
         ['84', 'Хүрээлэн буй орчин судлал', 'Цэрэнханд.Бат', '17B1NUM2417', '17B1NUM2417@stud.num.edu.mn', '99952248'],
         ['85', 'ХШУИС-ийн ерөнхий суурь хөтөлбөр', 'Энхбямба.Ган', '20B1NUM2114', '20B1NUM2114@stud.num.edu.mn',
          '95853355'],
         ['86', 'Хэрэглээний математик', 'Алтансүх.Алт', '20B1NUM2162', '20B1NUM2162@stud.num.edu.mn', '95632101'],
         ['87', 'Хэрэглээний математик', 'Батцэцэг.Мөн', '20B1NUM1071', '20B1NUM1071@stud.num.edu.mn', '80963666'],
         ['88', 'Хэрэглээний математик', 'Баярсайхан.Гал', '20B1NUM0175', '20B1NUM0175@stud.num.edu.mn', '86665507'],
         ['89', 'Хэрэглээний математик', 'Бямбадорж.Бат', '20B1NUM0115', '20B1NUM0115@stud.num.edu.mn', '80380733'],
         ['90', 'Хэрэглээний математик', 'Даваасүрэн.Цэд', '20B1NUM2262', '20B1NUM2262@stud.num.edu.mn', '80077060'],
         ['91', 'Хэрэглээний математик', 'Жавхлан.Ном', '20B1NUM2053', '20B1NUM2053@stud.num.edu.mn', '91776633'],
         ['92', 'Хэрэглээний математик', 'Жансерик.Мах', '20B1NUM1197', '20B1NUM1197@stud.num.edu.mn', '85955345'],
         ['93', 'Хэрэглээний математик', 'Мөнхсайхан.Эрд', '20B1NUM2075', '20B1NUM2075@stud.num.edu.mn', '99135912'],
         ['94', 'Хэрэглээний математик', 'Одбаяр.Бат', '20B1NUM2557', '20B1NUM2557@stud.num.edu.mn', '88719266'],
         ['95', 'Хэрэглээний математик', 'Сувданцоморлиг.Бол', '18B1NUM0786', '18B1NUM0786@stud.num.edu.mn',
          '94008599'],
         ['96', 'Хэрэглээний математик', 'Төмөртулга.Дор', '20B1NUM0444', '20B1NUM0444@stud.num.edu.mn', '80232482'],
         ['97', 'Хэрэглээний математик', 'Тэмүүжин.Эрд', '20B1NUM1970', '20B1NUM1970@stud.num.edu.mn', '99147798'],
         ['98', 'Хэрэглээний математик', 'Тэргэл.Ням', '19B1NUM1905', '19B1NUM1905@stud.num.edu.mn', '90696699'],
         ['99', 'Хэрэглээний математик', 'Хас-Очир.Бан', '20B1NUM0279', '20B1NUM0279@stud.num.edu.mn', '86178990'],
         ['100', 'Хэрэглээний математик', 'Энхтүвшин.Бат', '20B1NUM0490', '20B1NUM0490@stud.num.edu.mn', '80939348'],
         ['101', 'Хэрэглээний математик', 'Эрдэнэбат.Мөн', '18B1NUM3460', '18B1NUM3460@stud.num.edu.mn', '99132597'],
         ['102', 'Электроник', 'Тэнгис.Одг', '20B1NUM0243', '20B1NUM0243@stud.num.edu.mn', '94222801']]

    imports = [
        ['1', 'Статистик', 'Анударь.Эрд', '18B1NUM3011', '', ''],
        ['2', 'Статистик', 'Анхбат.Бям', '18B1NUM1056', '', ''],
        ['3', 'Статистик', 'Бадамгарав.Бая', '17B1NUM1636', '', ''],
        ['4', 'Статистик', 'Бат-оргил.Адъ', '19B1NUM1117', '', ''],
        ['5', 'Статистик', 'Баттөмөр.Там', '17B1NUM1425', '', ''],
        ['6', 'Статистик', 'Болортуул.Пүр', '19B1NUM1296', '', ''],
        ['7', 'Статистик', 'Бямбадорж.Лха', '19B1NUM0647', '', ''],
        ['8', 'Статистик', 'Ган-Эрдэнэ.Эрд', '17B1NUM1890', '', ''],
        ['9', 'Статистик', 'Даваадорж.Даг', '18B1NUM0691', '', ''],
        ['10', 'Статистик', 'Долгор.Бун', '19B1NUM0704', '', ''],
        ['11', 'Статистик', 'Дэлгэрцэцэг.Мөн', '17B1NUM1930', '', ''],
        ['12', 'Статистик', 'Зулзаяа.Буя', '18B1NUM2412', '', ''],
        ['13', 'Статистик', 'Мичидмаа.Сүх', '19B1NUM0297', '', ''],
        ['14', 'Статистик', 'Намуунзул.Бат', '19B1NUM0547', '', ''],
        ['15', 'Статистик', 'Нандин-Эрдэнэ.Зол', '18B1NUM0365', '', ''],
        ['16', 'Статистик', 'Отгонцэцэг.Бат', '19B1NUM1377', '', ''],
        ['17', 'Статистик', 'Цэрэндулам.Чад', '19B1NUM1040', '', ''],
        ['18', 'Статистик', 'Цэрэнзаяа.Цэв', '19B1NUM0690', '', ''],
        ['19', 'Статистик', 'Энхзул.Бат', '18B1NUM2243', '', ''],
        ['20', 'Хэрэглээний математик', 'Ануударь.Мөн', '17B1NUM1873', '', ''],
        ['21', 'Хэрэглээний математик', 'Бат-Оргил.Эрх', '17B1NUM2313', '', ''],
        ['22', 'Хэрэглээний математик', 'Дулмаа.Эрд', '18B1NUM1732', '', ''],
        ['23', 'Хэрэглээний математик', 'Ичинхорлоо.Бат', '16B1SEAS2550', '', ''],
        ['24', 'Хэрэглээний математик', 'Мөнхзаяа.Ган', '19B1NUM2290', '', ''],
        ['25', 'Хэрэглээний математик', 'Одонбаатар.Мөн', '18B1NUM3088', '', ''],
        ['26', 'Хэрэглээний математик', 'Соёлмаа.Гом', '17B1NUM1107', '', ''],
        ['27', 'Хэрэглээний математик', 'Тулпар.Арс', '18B1NUM2502', '', ''],
        ['28', 'Хэрэглээний математик', 'Хүслэн.Сэр', '19B1NUM0400', '', ''],
        ['29', 'Хэрэглээний математик', 'Шүрэнчимэг.Ван', '18B1NUM1025', '', '']]

    imports =[]

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
