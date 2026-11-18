from django.http import JsonResponse
from django.shortcuts import render
from olympiad.models import Result, Upload

from .forms import UploadForm
from olympiad.utils.params import get_int_param



def get_result_form(request):
    result_id = get_int_param(request.GET, 'result_id', 0)
    if result_id > 0:
        result = Result.objects.get(pk=result_id)
        upload = Upload(result_id=result_id)
        form = UploadForm(instance=upload)
        return render(request, "olympiad/upload_form.html", {'form': form, 'result': result})
    else:
        return JsonResponse({'status': 'failed'})


