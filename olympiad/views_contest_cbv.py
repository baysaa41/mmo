from django.views.generic import FormView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.forms import modelformset_factory
from django.shortcuts import render, redirect, get_object_or_404

from .models import Olympiad, Result, Upload
from .forms import ResultsForm, UploadForm
from .mixins import OlympiadAccessMixin, ResultsEnsureMixin
from django.db import transaction

ResultsFormSet = modelformset_factory(Result, form=ResultsForm, extra=0)


class StudentQuizView(LoginRequiredMixin, OlympiadAccessMixin, ResultsEnsureMixin, FormView):
    """Тест олимпиад бөглөх view"""
    template_name = 'olympiad/quiz/quiz.html'
    form_class = ResultsFormSet

    def get_queryset(self):
        """Хэрэглэгчийн result-үүдийг авах"""
        return Result.objects.filter(
            contestant=self.request.user,
            olympiad=self.olympiad
        ).select_related('problem').order_by('problem__order')

    def get_form_kwargs(self):
        """Form-д өгөх параметрүүд"""
        kwargs = super().get_form_kwargs()
        kwargs['queryset'] = self.get_queryset()
        return kwargs

    def get_context_data(self, **kwargs):
        """Template-д өгөх context"""
        context = super().get_context_data(**kwargs)
        context['items'] = self.get_queryset()
        context['olympiad'] = self.olympiad
        context['contestant'] = self.request.user
        return context

    def get(self, request, *args, **kwargs):
        """GET хүсэлт - олимпиад идэвхтэй эсэхийг шалгах"""
        if not self.olympiad.is_active():
            messages.error(request, 'Хугацаа дууссан байна.')
            return redirect('olympiad_end', olympiad_id=self.olympiad.id)

        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        """Form зөв үед - Bulk update ашиглах"""
        if self.olympiad.is_closed():
            messages.error(self.request, 'Хариулт авах хугацаа дууссан.')
            return redirect('olympiad_end', olympiad_id=self.olympiad.id)

        # Bulk update хийх (Хамгийн хурдан)
        with transaction.atomic():
            results_to_update = []

            for result_form in form:
                if result_form.has_changed():
                    result = result_form.instance
                    result.answer = result_form.cleaned_data.get('answer')
                    results_to_update.append(result)

            # Нэг query-ээр бүгдийг update хийх
            if results_to_update:
                Result.objects.bulk_update(results_to_update, ['answer'])

        messages.success(self.request, 'Хариултыг амжилттай хадгаллаа.')

        return render(self.request, 'olympiad/quiz/quiz_view_confirm.html', {
            'results': self.get_queryset(),
            'olympiad': self.olympiad
        })

    def form_invalid(self, form):
        """Form буруу үед"""
        messages.error(self.request, 'Хариулт хадгалахад алдаа гарлаа.')
        return super().form_invalid(form)


class StudentExamView(LoginRequiredMixin, OlympiadAccessMixin, ResultsEnsureMixin, TemplateView):
    """Уламжлалт олимпиад - зураг хуулах view"""
    template_name = 'olympiad/exam/exam.html'

    def get_context_data(self, **kwargs):
        """Template context"""
        context = super().get_context_data(**kwargs)
        context['results'] = Result.objects.filter(
            contestant=self.request.user,
            olympiad=self.olympiad
        ).select_related('problem').order_by('problem__order')
        context['olympiad'] = self.olympiad
        context['contestant'] = self.request.user
        return context

    def get(self, request, *args, **kwargs):
        """GET хүсэлт - олимпиад идэвхтэй эсэхийг шалгах"""
        if not self.olympiad.is_active():
            messages.info(request, 'Энэ олимпиадад оролцох эрхгүй байна.')
            return redirect('olympiad_home')

        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """POST хүсэлт - зураг хуулах"""
        form = UploadForm(request.POST, request.FILES)

        if form.is_valid():
            files = request.FILES.getlist('file')
            result_id = request.POST.get('result')

            # Олон файлыг нэг дор хадгалах
            uploads = [
                Upload(file=f, result_id=result_id)
                for f in files
            ]

            Upload.objects.bulk_create(uploads)

            # Result-ийн төлөвийг өөрчлөх
            Result.objects.filter(pk=result_id).update(state=1)

            messages.success(request, 'Файлыг амжилттай хуулсан.')

        return redirect('student_exam', olympiad_id=self.olympiad.id)


class StudentSupplementView(LoginRequiredMixin, TemplateView):
    """Нэмэлт материал илгээх view"""
    template_name = 'olympiad/supplement_exam.html'

    def dispatch(self, request, *args, **kwargs):
        olympiad_id = kwargs.get('olympiad_id')
        self.olympiad = get_object_or_404(Olympiad, pk=olympiad_id)

        # Хандалт шалгах
        access_denied = self.check_access()
        if access_denied:
            return access_denied

        return super().dispatch(request, *args, **kwargs)

    def check_access(self):
        """Supplement хандалт шалгах"""
        if not self.olympiad.is_grading:
            return render(
                self.request,
                'error.html',
                {'message': 'Нэмэлт материал хүлээн авах хугацаа дууссан.'}
            )

        # Групп шалгах
        if self.olympiad.group:
            if self.request.user not in self.olympiad.group.user_set.all():
                messages.info(
                    self.request,
                    f"Зөвхөн '{self.olympiad.group.name}' бүлгийн сурагчид оролцох боломжтой"
                )
                return redirect('olympiad_supplement_home')

        # Оролцсон эсэхийг шалгах
        if not self.request.user.is_staff:
            results = self.olympiad.result_set.filter(contestant=self.request.user)
            if not results.exists():
                return render(
                    self.request,
                    'error.html',
                    {'message': 'Зөвхөн энэ олимпиадад оролцсон сурагчид материал нэмж оруулах боломжтой.'}
                )

        return None

    def get_context_data(self, **kwargs):
        """Template context"""
        context = super().get_context_data(**kwargs)

        # Result-үүд үүсгэх
        self.ensure_results_exist()

        context['results'] = Result.objects.filter(
            contestant=self.request.user,
            olympiad=self.olympiad
        ).select_related('problem').order_by('problem__order')
        context['olympiad'] = self.olympiad
        context['contestant'] = self.request.user
        return context

    def ensure_results_exist(self):
        """Result-үүд үүсгэх"""
        user = self.request.user
        problems = self.olympiad.problem_set.all().order_by('order')

        for problem in problems:
            Result.objects.get_or_create(
                contestant=user,
                olympiad=self.olympiad,
                problem=problem
            )

    def post(self, request, *args, **kwargs):
        """Supplement файл хуулах"""
        form = UploadForm(request.POST, request.FILES)

        if form.is_valid():
            files = request.FILES.getlist('file')
            result_id = request.POST.get('result')

            uploads = [
                Upload(file=f, result_id=result_id, is_accepted=False)
                for f in files
            ]
            Upload.objects.bulk_create(uploads)

            # Result төлөв өөрчлөх
            Result.objects.filter(pk=result_id).update(state=3)

            messages.success(request, 'Нэмэлт материалыг амжилттай илгээлээ.')

        return redirect('student_supplement_view', olympiad_id=self.olympiad.id)


class ContestEndView(LoginRequiredMixin, TemplateView):
    """Олимпиад дууссаны мэдэгдэл"""
    template_name = 'olympiad/exam/end_note.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['olympiad'] = get_object_or_404(Olympiad, pk=kwargs['olympiad_id'])
        return context