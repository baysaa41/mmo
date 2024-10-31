import json
from audioop import error

from django.http import HttpResponse, JsonResponse, FileResponse
from django.shortcuts import render, redirect, reverse
from .models import User, Result, Problem, Olympiad

def save_json_to_file(data, filename='json_results.json'):
    with open(filename, 'w') as f:
        json.dump(data, f)
    return filename
def olympiad_results_json(request, olympiad_id):
    olympiad = Olympiad.objects.get(pk=olympiad_id)
    file = save_json_to_file(olympiad.json_results)
    file_path = f'/path/to/json_results_{file}'
    return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=file)


def results(request, olympiad_id):
    try:
        olympiad = Olympiad.objects.get(pk=olympiad_id)
    except Olympiad.DoesNotExist:
        return render(request, 'error.html', {'error': 'olympiad not found'})

    return render(request, 'olympiad/result_handler.html', {'olympiad': olympiad})
