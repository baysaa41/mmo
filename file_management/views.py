from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from django.views.decorators.http import require_POST

from schools.models import School
from olympiad.models import SchoolYear
from accounts.models import Province
from .models import FileUpload, FileAccessLog
from .forms import FileUploadForm, TrainingMaterialForm
from django.contrib.auth.models import User
import mimetypes
import os


@login_required
def upload_file(request):
    if request.user.is_staff:
        if request.method == "POST":
            form = FileUploadForm(request.POST, request.FILES)
            if form.is_valid():
                file_instance = form.save(commit=False)
                file_instance.uploader = request.user
                file_instance.save()
                return redirect('file_list')
        else:
            form = FileUploadForm()
        return render(request, 'file_management/upload_file.html', {'form': form})
    else:
        return render(request, 'error.html', {'message': 'Та энэ хуудсанд хандах эрхгүй.'})


@login_required
def download_file(request, file_id):
    file_instance = get_object_or_404(FileUpload, id=file_id)
    # Бэлтгэлийн материалыг нэвтэрсэн бүх хэрэглэгч татаж болно,
    # бусад (заавар) файлыг зөвхөн сургууль/аймгийн ажилтнууд
    if file_instance.kind == FileUpload.Kind.TRAINING or is_manager(request.user.id):
        file_name = os.path.basename(file_instance.file.name)
        mime_type, _ = mimetypes.guess_type(file_name)

        # Track download in FileAccessLog
        FileAccessLog.objects.create(file=file_instance, user=request.user)

        # Storage API-аар унших (S3 болон local storage-д хоёуланд нь ажиллана;
        # .path нь S3Boto3Storage дээр дэмжигдэхгүй тул ашиглаж болохгүй)
        with file_instance.file.open('rb') as file:
            response = HttpResponse(file.read(), content_type=mime_type)
            response['Content-Disposition'] = f'attachment; filename="{file_name}"'
            return response
    else:
        return render(request, 'error.html', {'message': 'Та сургуулийн хаягаар нэвтрээгүй байна.'})


@login_required
def file_list(request):
    if is_manager(request.user.id):
        # Хичээлийн жил сонгох (query parameter ашиглана)
        selected_year_id = request.GET.get('year', None)

        # Бүх хичээлийн жилүүдийг авах
        school_years = SchoolYear.objects.all()

        # Хэрэв жил сонгогдоогүй бол одоогийн жилийг сонгоно
        if selected_year_id:
            selected_year = get_object_or_404(SchoolYear, id=selected_year_id)
        else:
            # Одоогийн хичээлийн жилийг авах, байхгүй бол хамгийн сүүлийнх
            selected_year = SchoolYear.get_current() or SchoolYear.objects.first()

        # Файлуудыг хичээлийн жилээр шүүж, сүүлд оруулсан эхэнд эрэмбэлэх
        if selected_year:
            files = FileUpload.objects.filter(school_year=selected_year).select_related('uploader', 'school_year')
        else:
            # Хэрэв хичээлийн жил байхгүй бол бүх файлыг харуулна
            files = FileUpload.objects.all().select_related('uploader', 'school_year')

        # Аль хэдийн нийтлэлийн хавсралт болсон файлыг энэ жагсаалтад харуулахгүй
        # (тухайн файл нийтлэл дээрээ өөрөө хавсралтаар харагдана)
        files = files.filter(posts__isnull=True)

        # Бэлтгэлийн материал тусдаа хуудсанд (training_materials) харагдана
        files = files.filter(kind=FileUpload.Kind.GENERAL)

        # Файл бүрийн татагдсан тоог тооцоолох
        files = files.annotate(download_count=Count('access_logs'))

        context = {
            'files': files,
            'school_years': school_years,
            'selected_year': selected_year,
        }

        return render(request, 'file_management/file_list.html', context)
    else:
        return render(request, 'error.html', {'message': 'Та сургуулийн хаягаар нэвтрээгүй байна.'})


@login_required
@user_passes_test(lambda u: u.is_staff)
@require_POST
def delete_file(request, file_id):
    file_instance = get_object_or_404(FileUpload, id=file_id)
    is_training = file_instance.kind == FileUpload.Kind.TRAINING
    file_instance.file.delete(save=False)
    file_instance.delete()
    return redirect('training_materials' if is_training else 'file_list')


def training_materials(request):
    """
    Олимпиадын бэлтгэлийн материалын жагсаалт (жишээ нь: EGMO бэлтгэл 2026).
    Жагсаалтыг хэн ч харж болно, татахын тулд нэвтэрсэн байх шаардлагатай.
    """
    materials = (
        FileUpload.objects.filter(kind=FileUpload.Kind.TRAINING)
        .select_related('school_year')
        .annotate(download_count=Count('access_logs'))
        .order_by('-school_year__name', 'title')
    )

    school_years = SchoolYear.objects.filter(uploaded_files__kind=FileUpload.Kind.TRAINING).distinct()
    selected_year = None
    selected_year_id = request.GET.get('year')
    if selected_year_id:
        selected_year = get_object_or_404(SchoolYear, id=selected_year_id)
        materials = materials.filter(school_year=selected_year)

    return render(request, 'file_management/training_materials.html', {
        'materials': materials,
        'school_years': school_years,
        'selected_year': selected_year,
    })


@login_required
@user_passes_test(lambda u: u.is_staff)
def edit_file(request, file_id):
    """Файлын мэдээлэл (тайлбар, хичээлийн жил, бэлтгэлийн гарчиг/багш нар) засах. Файлыг солих нь заавал биш."""
    file_instance = get_object_or_404(FileUpload, id=file_id)
    is_training = file_instance.kind == FileUpload.Kind.TRAINING
    form_class = TrainingMaterialForm if is_training else FileUploadForm
    back_url = 'training_materials' if is_training else 'file_list'

    if request.method == 'POST':
        old_file = file_instance.file.name
        form = form_class(request.POST, request.FILES, instance=file_instance)
        if form.is_valid():
            form.save()
            # Шинэ файл оруулсан бол хуучныг storage-оос устгана
            if 'file' in request.FILES and old_file and old_file != file_instance.file.name:
                file_instance.file.storage.delete(old_file)
            return redirect(back_url)
    else:
        form = form_class(instance=file_instance)

    return render(request, 'file_management/edit_file.html', {
        'form': form,
        'file': file_instance,
        'back_url': back_url,
    })


@login_required
@user_passes_test(lambda u: u.is_staff)
def upload_training_material(request):
    if request.method == 'POST':
        form = TrainingMaterialForm(request.POST, request.FILES)
        if form.is_valid():
            material = form.save(commit=False)
            material.uploader = request.user
            material.save()
            return redirect('training_materials')
    else:
        form = TrainingMaterialForm()
    return render(request, 'file_management/upload_training_material.html', {'form': form})


def is_manager(user_id):
    """
    Хэрэглэгч файлуудад хандах эрхтэй эсэхийг шалгах.
    Staff, школын moderator, эсвэл аймгийн manager бол эрхтэй.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return False

    # Staff эрх
    if user.is_staff:
        return True

    # Школын moderator эрх
    if School.objects.filter(user=user).exists():
        return True

    # Школын manager эрх
    if School.objects.filter(manager=user).exists():
        return True

    # Аймгийн удирдах ажилтан/бүртгэгч багш эрх
    if Province.objects.filter(Q(contact_person=user) | Q(contact_person2=user) | Q(registrar=user)).exists():
        return True

    # Province_{id}_Managers group эрх
    if user.groups.filter(name__startswith='Province_', name__endswith='_Managers').exists():
        return True

    return False