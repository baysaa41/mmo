# accounts/views/importers.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .. import services
from ..models import UserMails, User

@login_required()
def import_file(request):
    if request.method == "GET":
        return render(request, 'accounts/upload_file.html', {'error': 0})

    excel_file = request.FILES.get("excel_file")
    if not excel_file:
        context = {'error': True, 'messages': ["Excel файл сонгоно уу."]}
        return render(request, 'accounts/upload_file.html', context)

    # Call the main service function to handle all the logic
    success, messages, teacher = services.process_excel_import(excel_file, request.user)

    if success and teacher:
        # If import is successful, create the confirmation email
        text = '\n'.join(messages)
        html_content = '<br>'.join(f"<p>{msg}</p>" for msg in messages)
        UserMails.objects.create(
            subject='ММОХ бүртгэлийн мэдээлэл',
            text=text,
            text_html=html_content,
            from_email='no-reply@mmo.mn',
            to_email=teacher.email,
            is_sent=False
        )
        # Also send a copy to the person who uploaded
        if teacher.id != request.user.id:
            UserMails.objects.create(
                subject='ММОХ бүртгэлийн мэдээлэл (Хуулбар)',
                text=text,
                text_html=html_content,
                from_email='no-reply@mmo.mn',
                to_email=request.user.email,
                is_sent=False
            )

    context = {'error': not success, 'messages': messages}
    return render(request, 'accounts/upload_file.html', context)