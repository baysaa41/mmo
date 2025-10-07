from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.db import transaction
from .models import Olympiad, Result

class OlympiadAccessMixin:
    """Олимпиадын хандалт шалгах mixin"""

    def dispatch(self, request, *args, **kwargs):
        olympiad_id = kwargs.get('olympiad_id')
        self.olympiad = get_object_or_404(
            Olympiad.objects.select_related('group', 'level', 'school_year'),
            pk=olympiad_id
        )

        # Хандах эрх шалгах
        access_denied = self.check_access()
        if access_denied:
            return access_denied

        return super().dispatch(request, *args, **kwargs)

    def check_access(self):
        """Бүх шалгалтыг хийх"""
        user = self.request.user
        olympiad = self.olympiad

        # Групп шалгах
        if olympiad.group and user not in olympiad.group.user_set.all():
            messages.info(
                self.request,
                f"Зөвхөн '{olympiad.group.name}' бүлгийн сурагчид оролцох боломжтой"
            )
            return redirect('olympiad_home')

        # Цаг шалгах
        if not olympiad.is_started():
            messages.info(self.request, 'Олимпиадын бодолт эхлээгүй байна.')
            return redirect('olympiad_home')

        if olympiad.is_finished():
            messages.info(self.request, 'Олимпиадын бодолт дууссан байна.')
            return redirect('olympiad_home')

        return None


class ResultsEnsureMixin:
    """Result-үүдийг автоматаар үүсгэх mixin"""

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)

        # Result-үүд байгаа эсэхийг шалгах
        if hasattr(self, 'olympiad'):
            self.ensure_results_exist()

        return response

    def ensure_results_exist(self):
        """Result-үүдийг bulk create ашиглан үүсгэх"""
        user = self.request.user
        olympiad = self.olympiad

        # Одоо байгаа result-үүдийн problem_id-г авах
        existing_problem_ids = set(
            Result.objects.filter(
                contestant=user,
                olympiad=olympiad
            ).values_list('problem_id', flat=True)
        )

        # Шинээр үүсгэх result-үүд
        problems = olympiad.problem_set.all().order_by('order')
        results_to_create = [
            Result(contestant=user, olympiad=olympiad, problem=problem)
            for problem in problems
            if problem.id not in existing_problem_ids
        ]

        if results_to_create:
            Result.objects.bulk_create(results_to_create, ignore_conflicts=True)