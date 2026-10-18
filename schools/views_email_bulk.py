"""Багш сурагчдынхаа имэйлийг Excel-ээр бөөнөөр солих (нэвтрэлтгүй холбоос, schools.email_bulk)."""
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import email_bulk as bulk
from . import round1_links as links

SESSION_KEY = 'email_bulk_plan'
SHOW_LIMIT = 300
XLSX_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _context(token):
    email = links.read_token(token)
    anchor = bulk.anchor_uid(token)
    return (email, anchor) if email and anchor else (None, None)


def email_bulk_download_view(request, token):
    email, anchor = _context(token)
    if not email:
        return render(request, 'schools/round1/invalid.html', status=404)
    data, _n = bulk.build_workbook(email, anchor)
    resp = HttpResponse(data, content_type=XLSX_TYPE)
    resp['Content-Disposition'] = 'attachment; filename="mmo63_student_emails.xlsx"'
    return resp


@require_POST
def email_bulk_upload_view(request, token):
    email, anchor = _context(token)
    if not email:
        return render(request, 'schools/round1/invalid.html', status=404)
    f = request.FILES.get('file')
    if not f or not f.name.lower().endswith('.xlsx'):
        messages.error(request, 'Татсан .xlsx файлаа сонгоно уу.')
        return redirect('round1_info', token=token)
    if f.size > bulk.MAX_UPLOAD_BYTES:
        messages.error(request, 'Файл хэт том байна (5 MB-аас бага байх ёстой).')
        return redirect('round1_info', token=token)
    try:
        plan = bulk.build_plan(email, anchor, f)
    except Exception as exc:  # эвдэрсэн/буруу формат — хэрэглэгчид ойлгомжтой мэдэгдэнэ
        messages.error(request, f'Файлыг уншиж чадсангүй: {exc}')
        return redirect('round1_info', token=token)
    request.session[SESSION_KEY] = {'token': token, 'pairs': [[c[0], c[2]] for c in plan['changes']]}
    return render(request, 'schools/round1/email_bulk_preview.html', {
        'token': token, 'email': email,
        'changes': plan['changes'][:SHOW_LIMIT], 'change_count': len(plan['changes']),
        'rejected': plan['rejected'][:SHOW_LIMIT], 'rejected_count': len(plan['rejected']),
        'unchanged': plan['unchanged'], 'reasons': sorted(plan['reasons'].items(), key=lambda x: -x[1]),
        'limit': SHOW_LIMIT,
    })


@require_POST
def email_bulk_confirm_view(request, token):
    email, anchor = _context(token)
    if not email:
        return render(request, 'schools/round1/invalid.html', status=404)
    saved = request.session.pop(SESSION_KEY, None)
    if not saved or saved.get('token') != token or not saved.get('pairs'):
        messages.error(request, 'Баталгаажуулах өөрчлөлт олдсонгүй. Файлаа дахин оруулна уу.')
        return redirect('round1_info', token=token)
    done, rejected = bulk.apply_changes(email, anchor, [(int(u), n) for u, n in saved['pairs']])
    if done:
        from .tasks import send_email_change_links_task
        transaction.on_commit(lambda: send_email_change_links_task.delay(done))
        messages.success(request, f'{len(done)} аккаунтын имэйл солигдлоо. Шинэ хаяг бүр рүү нууц үг '
                                  'тохируулах холбоос илгээж байна.')
    if rejected:
        messages.warning(request, f'{len(rejected)} мөр баталгаажуулах үед татгалзагдлаа (хэн нэгэн хаягийг '
                                  'завсар авсан байж болно). Файлаа дахин оруулж шалгана уу.')
    if not done and not rejected:
        messages.info(request, 'Өөрчлөх зүйл алга.')
    return redirect('round1_info', token=token)
