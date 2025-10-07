from django.http import JsonResponse
from django.shortcuts import render
from olympiad.models import Result, Upload

from .forms import UploadForm



def get_result_form(request):
    result_id = int(request.GET.get('result_id', 0))
    if result_id > 0:
        result = Result.objects.get(pk=result_id)
        upload = Upload(result_id=result_id)
        form = UploadForm(instance=upload)
        return render(request, "olympiad/upload_form.html", {'form': form, 'result': result})
    else:
        return JsonResponse({'status': 'failed'})


