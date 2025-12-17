from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.db import transaction
from .models import Olympiad, Result


class OlympiadAccessMixin:
    """Олимпиадын хандалт/хугацаа шалгах mixin."""

    def dispatch(self, request, *args, **kwargs):
        olympiad_id = kwargs.get('olympiad_id')
        self.olympiad = get_object_or_404(
            Olympiad.objects.select_related('group', 'level', 'school_year'),
            pk=olympiad_id
        )

        access_denied = self.check_access()
        if access_denied:
            return access_denied

        return super().dispatch(request, *args, **kwargs)

    def check_access(self):
        """Групп ба цагийн шалгалтууд."""
        user = self.request.user
        olympiad = self.olympiad

        if olympiad.group and user not in olympiad.group.user_set.all():
            messages.info(
                self.request,
                f"Зөвхөн '{olympiad.group.name}' бүлгийн сурагчид оролцох боломжтой"
            )
            return redirect('olympiad_home')

        if not olympiad.is_started():
            messages.info(self.request, 'Олимпиадын бодолт эхлээгүй байна.')
            return redirect('olympiad_home')

        if olympiad.is_finished():
            messages.info(self.request, 'Олимпиадын бодолт дууссан байна.')
            return redirect('olympiad_home')

        return None


class ResultsEnsureMixin:
    """
    Сурагч тухайн олимпиадад орж ирмэгц,
    тухайн олимпиадын бүх problem-д харгалзах Result-уудыг автоматаар бий болгоно.
    """

    def dispatch(self, request, *args, **kwargs):
        # ⚠️ OlympiadAccessMixin-ээс self.olympiad эхэлж оноогдсон байх ёстой.
        if not hasattr(self, 'olympiad'):
            raise AttributeError(
                "ResultsEnsureMixin requires OlympiadAccessMixin (олимпиад эхлээд оноогдсон байх ёстой)."
            )

        # ✅ form/render-оос ӨМНӨ Result-уудыг заавал үүсгэнэ
        self.ensure_results_exist()
        return super().dispatch(request, *args, **kwargs)

    def ensure_results_exist(self):
        user = self.request.user
        olympiad = self.olympiad

        # Одоо байгаа Result-үүдийн problem_id жагсаалтыг авна
        existing_problem_ids = set(
            Result.objects.filter(
                contestant=user, olympiad=olympiad
            ).values_list('problem_id', flat=True)
        )

        problems = olympiad.problem_set.all().order_by('order')

        results_to_create = [
            Result(contestant=user, olympiad=olympiad, problem=problem)
            for problem in problems
            if problem.id not in existing_problem_ids
        ]

        if results_to_create:
            # Аюулгүй байдлаар нэг дор үүсгэнэ
            with transaction.atomic():
                Result.objects.bulk_create(results_to_create, ignore_conflicts=True)
