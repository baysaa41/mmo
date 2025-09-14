# accounts/views/email.py

from django.shortcuts import render, redirect, get_object_or_404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.core.mail import get_connection, EmailMultiAlternatives, EmailMessage

from ..models import UserMails
from ..forms import EmailForm
from schools.models import School

import re

# create_diploms_mail, create_emails, create_mails зэрэг функцууд энд орно
# ...

@login_required(login_url='/accounts/login/')
@login_required
def send_email_to_schools(request):
    if request.method == "POST":
        form = EmailForm(request.POST, request.FILES)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            attachments = request.FILES.getlist('attachments')

            # --- ИЛГЭЭХЭЭС ӨМНӨ ЦЭВЭРЛЭХ ХЭСЭГ ---
            cleaned_subject = clean_string(subject)
            cleaned_message = clean_string(message)
            # ------------------------------------

            schools = School.objects.filter(pk=498)
            print(schools.count())

            sent_count = 0
            fail_count = 0

            for school in schools:
                try:
                    email = EmailMessage(
                        subject=cleaned_subject,  # <-- Цэвэрлэсэн хувьсагчийг ашиглана
                        body=cleaned_message,   # <-- Цэвэрлэсэн хувьсагчийг ашиглана
                        from_email='info@mmo.mn',
                        to=[school.user.email]
                    )

                    for attachment in attachments:
                        attachment.seek(0)
                        email.attach(attachment.name, attachment.read(), attachment.content_type)

                    if email.send():
                        school.is_sent_confirmation = True
                        school.save()
                        sent_count += 1
                    else:
                        fail_count += 1

                except Exception as e:
                    messages.error(request, f"'{school.name}' сургууль руу илгээхэд алдаа гарлаа: {e}")
                    print(f"Failed to send email to {school.name}: {e}")
                    fail_count += 1

            if sent_count > 0:
                messages.success(request, f"{sent_count} сургууль руу и-мэйлийг амжилттай илгээлээ.")
            if fail_count > 0:
                messages.warning(request, f"{fail_count} сургууль руу и-мэйл илгээхэд алдаа гарлаа.")

            print(sent_count,fail_count)

            return redirect('school_moderators_list')
    else:
        form = EmailForm()
    return render(request, 'accounts/send_email.html', {'form': form})

def send_mass_html_mail(request):
    connection = get_connection(fail_silently=False)
    messages = []
    uemails = UserMails.objects.filter(is_sent=False)[:50]

    for uemail in uemails:
        tracking_url = request.build_absolute_uri(reverse('track_email_open', args=[uemail.tracking_token]))
        message_html = f"{uemail.text_html}<br><br> <a href='{tracking_url}'>Энд</a> товшиж баталгаажуул."

        message = EmailMultiAlternatives(uemail.subject, uemail.text, uemail.from_email, [uemail.to_email])
        message.attach_alternative(message_html, 'text/html')
        messages.append(message)

        uemail.is_sent = True
        uemail.save()

    sent_count = connection.send_messages(messages)
    return HttpResponse(f"{sent_count} emails sent successfully.")

def track_email_open(request, token):
    uemail = get_object_or_404(UserMails, tracking_token=token)
    uemail.is_opened = True
    uemail.save()
    return HttpResponse("Thank you for confirming this email.")

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

@login_required(login_url='/accounts/login/')
def send_email_with_attachments(request):
    if request.method == 'POST':
        form = EmailForm(request.POST, request.FILES)
        if form.is_valid():
            schools = School.objects.all()
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            from_email = 'MMO <no-reply@mmo.mn>'
            recipients = [school.user.email for school in schools]
            batch_size = 50  # Adjust as needed
            for i in range(0, len(recipients), batch_size):
                batch_recipients = recipients[i:i+batch_size]

                email = EmailMessage(subject, message, from_email, batch_recipients)
                email.content_subtype = "html"

                # Attach files
                attachments = request.FILES.getlist('attachments')
                for attachment in attachments:
                    attachment.seek(0)
                    email.attach(attachment.name, attachment.read(), attachment.content_type)

                # Send the email
                email.send()
                # print(email)

            return render(request, 'accounts/success.html', {'message': 'Email sent successfully.'})

    else:
        form = EmailForm()

    return render(request, 'accounts/send_email.html', {'form': form})