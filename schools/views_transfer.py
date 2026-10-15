from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import transfers
from .models import School, StudentTransfer

Status = StudentTransfer.Status


def _school_or_denied(request, school_id):
    school = get_object_or_404(School.objects.select_related('province', 'group'), id=school_id)
    if not school.user_has_access(request.user):
        messages.error(request, 'Та энэ сургуулийг удирдах эрхгүй.')
        return school, render(request, 'error.html', {'message': 'Хандах эрхгүй.'})
    return school, None


def _ids(values):
    return [int(v) for v in values if str(v).strip().isdigit()]


@login_required
def transfer_students_view(request, school_id):
    """Сонгосон сурагчдыг өөр сургууль руу шилжүүлэх хүсэлт илгээх."""
    school, denied = _school_or_denied(request, school_id)
    if denied:
        return denied

    if request.method == 'POST':
        user_ids = _ids(request.POST.getlist('user_ids'))
    else:
        user_ids = _ids(request.GET.get('user_ids', '').split(','))
    students = list(User.objects.filter(id__in=user_ids, groups=school.group_id)
                    .select_related('data__grade').order_by('last_name', 'first_name'))

    if request.method == 'POST':
        to_school = School.objects.select_related('province').filter(
            id=request.POST.get('to_school') or 0).first()
        if not students:
            messages.error(request, 'Шилжүүлэх сурагч сонгоогүй байна.')
        elif to_school is None:
            messages.error(request, 'Хүлээн авах сургуулиа сонгоно уу.')
        else:
            created, skipped = transfers.request_transfers(
                students, school, to_school, by=request.user, note=request.POST.get('note', '').strip())
            if created:
                link = request.build_absolute_uri(reverse('school_transfers', args=[to_school.id]))
                transfers.notify_requested(created, school, to_school, link)
                messages.success(
                    request,
                    f'{len(created)} сурагчийг {to_school.name} сургууль руу шилжүүлэх хүсэлт илгээлээ. '
                    'Тэр сургуулийн бүртгэгч багш хүлээн авсны дараа сурагчид шилжинэ.')
            for user, reason in skipped:
                messages.warning(request, f'{user.last_name} {user.first_name}: {reason}')
            if created:
                return redirect('school_transfers', school_id=school.id)

    schools = (School.objects.exclude(pk=school.pk).exclude(group__isnull=True)
               .select_related('province').order_by('province__name', 'name'))
    same = [s for s in schools if s.province_id == school.province_id]
    other = [s for s in schools if s.province_id != school.province_id]
    return render(request, 'schools/transfer_students.html', {
        'school': school,
        'students': students,
        'same_province_schools': same,
        'other_schools': other,
        'selected_to_school': request.POST.get('to_school', ''),
        'note': request.POST.get('note', ''),
    })


@login_required
def school_transfers_view(request, school_id):
    """Ирсэн болон илгээсэн шилжүүлгийн хүсэлтүүд."""
    school, denied = _school_or_denied(request, school_id)
    if denied:
        return denied

    if request.method == 'POST':
        action = request.POST.get('action')
        ids = _ids(request.POST.getlist('transfer_ids'))
        fn = {'accept': transfers.accept, 'reject': transfers.reject, 'cancel': transfers.cancel}.get(action)
        if fn is None or not ids:
            messages.error(request, 'Хүсэлт сонгоогүй байна.')
            return redirect('school_transfers', school_id=school.id)

        done = [t for t in (fn(i, school, by=request.user) for i in ids) if t is not None]
        if action in ('accept', 'reject') and done:
            transfers.notify_decided(done, school, accepted=(action == 'accept'))
        word = {'accept': 'хүлээн авлаа', 'reject': 'татгалзлаа', 'cancel': 'цуцаллаа'}[action]
        messages.success(request, f'{len(done)} хүсэлтийг {word}.')
        if len(done) < len(ids):
            messages.warning(request, f'{len(ids) - len(done)} хүсэлт аль хэдийн шийдэгдсэн байна.')
        return redirect('school_transfers', school_id=school.id)

    base = StudentTransfer.objects.select_related(
        'user__data__grade', 'from_school__province', 'to_school__province', 'requested_by', 'decided_by')
    return render(request, 'schools/school_transfers.html', {
        'school': school,
        'incoming': base.filter(to_school=school, status=Status.PENDING).order_by('from_school__name', 'user__last_name'),
        'outgoing': base.filter(from_school=school, status=Status.PENDING).order_by('to_school__name', 'user__last_name'),
        'history': base.filter(Q(to_school=school) | Q(from_school=school)).exclude(status=Status.PENDING).order_by('-decided_at')[:100],
    })


def incoming_transfer_count(school):
    return StudentTransfer.objects.filter(to_school=school, status=Status.PENDING).count()
