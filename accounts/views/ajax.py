from django.http import JsonResponse
from schools.models import School

def load_schools(request):
    province_id = request.GET.get('province_id')
    # province_id-г ашиглан зөвхөн тухайн аймагт хамаарах сургуулиудыг шүүх
    schools = School.objects.filter(province_id=province_id).order_by('name')
    # Сургуулиудын ID болон нэрийг JSON хэлбэрээр буцаах
    return JsonResponse(list(schools.values('id', 'name')), safe=False)