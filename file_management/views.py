from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Count

from schools.models import School
from olympiad.models import SchoolYear
from .models import FileUpload, FileAccessLog
from .forms import FileUploadForm
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
    if is_manager(request.user.id):
        file_instance = get_object_or_404(FileUpload, id=file_id)
        file_path = file_instance.file.path
        file_name = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)

        # Track download in FileAccessLog
        FileAccessLog.objects.create(file=file_instance, user=request.user)

        with open(file_path, 'rb') as file:
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

        # Хэрэв жил сонгогдоогүй бол сүүлийн жилийг сонгоно
        if selected_year_id:
            selected_year = get_object_or_404(SchoolYear, id=selected_year_id)
        else:
            selected_year = school_years.first()  # ordering = ['-name'] учраас эхний нь сүүлийнх

        # Файлуудыг хичээлийн жилээр шүүж, сүүлд оруулсан эхэнд эрэмбэлэх
        if selected_year:
            files = FileUpload.objects.filter(school_year=selected_year).select_related('uploader', 'school_year')
        else:
            # Хэрэв хичээлийн жил байхгүй бол бүх файлыг харуулна
            files = FileUpload.objects.all().select_related('uploader', 'school_year')

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


def is_manager(user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return False
    if School.objects.filter(user=user).exists() or user.is_staff:
        return True
    else:
        return False