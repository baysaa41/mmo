from django.http import HttpResponse, JsonResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404
from olympiad.models import Olympiad, Result, SchoolYear, Award, Problem, OlympiadGroup, ScoreSheet
from schools.models import School
from accounts.models import Province, Zone, UserMeta
from django.forms import modelformset_factory
from .forms import ResultsForm, ChangeScoreSheetSchoolForm
import pandas as pd
import numpy as np
from django_pandas.io import read_frame
from django.db import connection
from django.contrib.auth.models import User, Group
from datetime import datetime, timezone
from olympiad.utils.data import adjusted_int_name
import csv
import os, io
import json
import re
from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django_tex.core import render_template_with_context
from django.db.models import Count
from django.shortcuts import redirect


from django.db.models import Count, Avg, Max, Min

from django.core.cache import cache

@staff_member_required
def olympiad_problem_stats(request, olympiad_id):
    cache_key = f"olympiad_stats_{olympiad_id}"
    data = cache.get(cache_key)
    if not data:
        olympiad = get_object_or_404(Olympiad, pk=olympiad_id)
        problems = olympiad.problem_set.order_by('order')

        problem_stats = []
        for problem in problems:
            results = Result.objects.filter(problem=problem, score__isnull=False)
            stats = results.aggregate(
                submissions=Count('id'),
                avg=Avg('score'),
                max=Max('score'),
                min=Min('score')
            )
            province_stats = []
            for prov in Province.objects.all().order_by("id"):
                prov_results = results.filter(contestant__data__province=prov)
                total = prov_results.count()
                gt_zero = prov_results.filter(score__gt=0).count()
                full = prov_results.filter(score=problem.max_score).count()
                province_stats.append({
                    "province": prov.name,
                    "total": total,
                    "gt_zero": gt_zero,
                    "full": full,
                })
            problem_stats.append({
                "problem": problem,
                "stats": stats,
                "province_stats": province_stats,
            })

        data = {
            "olympiad": olympiad,
            "problem_stats": problem_stats,
        }
        cache.set(cache_key, data, timeout=None)  # хугацаагүй хадгална

    return render(request, "olympiad/stats/olympiad_problem_stats.html", data)


ResultsFormSet = modelformset_factory(Result, form=ResultsForm, extra=0)


