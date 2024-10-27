from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

from schools.models import School
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
        return render(request, 'error.html', {'error': 'Та энэ хуудсанд хандах эрхгүй.'})


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
        return render(request, 'error.html', {'error': 'Та сургуулийн хаягаар нэвтрээгүй байна.'})

@login_required
def file_list(request):
    if is_manager(request.user.id):
        # Retrieve all uploaded files
        files = FileUpload.objects.all()
        return render(request, 'file_management/file_list.html', {'files': files})
    else:
        return render(request, 'error.html', {'error': 'Та сургуулийн хаягаар нэвтрээгүй байна.'})

def is_manager(user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return False
    if School.objects.filter(user=user).exists() or user.is_staff:
        return True
    else:
        return False