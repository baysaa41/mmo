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
        """POST хүсэлт - зураг хуулах (сайжруулсан)"""
        form = UploadForm(request.POST, request.FILES)

        if form.is_valid():
            files = request.FILES.getlist('file')

            # Файл хуулсан эсэхийг шалгах
            if not files:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'Зураг сонгоно уу.'
                    }, status=400)
                else:
                    messages.error(request, 'Зураг сонгоно уу.')
                    context = self.get_context_data(**kwargs)
                    context['form'] = form
                    return render(request, self.template_name, context)

            result_id = request.POST.get('result')

            # Файл бүрийг шалгаж хуулах
            uploaded_files = []
            failed_files = []

            ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
            MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

            for file in files:
                # Файлын extension шалгах
                file_ext = file.name.split('.')[-1].lower()
                if file_ext not in ALLOWED_EXTENSIONS:
                    failed_files.append({
                        'name': file.name,
                        'reason': f'Зөвхөн {", ".join(ALLOWED_EXTENSIONS)} файл хүлээн авна.'
                    })
                    continue

                # Файлын хэмжээ шалгах
                if file.size > MAX_FILE_SIZE:
                    failed_files.append({
                        'name': file.name,
                        'reason': f'Файлын хэмжээ 10MB-аас бага байх ёстой. ({file.size / 1024 / 1024:.1f}MB)'
                    })
                    continue

                # Амжилттай бол хадгалах
                try:
                    upload = Upload(file=file, result_id=result_id)
                    upload.save()
                    uploaded_files.append({
                        'name': file.name,
                        'url': upload.file.url,
                        'id': upload.id
                    })
                except Exception as e:
                    failed_files.append({
                        'name': file.name,
                        'reason': f'Хадгалахад алдаа гарлаа: {str(e)}'
                    })

            # Result-ийн төлөвийг өөрчлөх (хоть 1 файл амжилттай бол)
            if uploaded_files:
                Result.objects.filter(pk=result_id).update(state=1)

            # Мессеж үүсгэх
            if uploaded_files and not failed_files:
                message = f'✅ {len(uploaded_files)} файлыг амжилттай хуулсан.'
                success = True
            elif uploaded_files and failed_files:
                message = f'⚠️ {len(uploaded_files)} файл амжилттай, {len(failed_files)} файл амжилтгүй.'
                success = True
            else:
                message = f'❌ Бүх файл амжилтгүй болсон.'
                success = False

            # AJAX request бол JSON буцаах
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': success,
                    'message': message,
                    'uploaded_files': uploaded_files,
                    'failed_files': failed_files
                })

            # Энгийн request бол message + redirect
            if success:
                messages.success(request, message)
            else:
                messages.error(request, message)

            # Амжилтгүй файлуудын дэлгэрэнгүй мэдээлэл
            if failed_files:
                for failed in failed_files:
                    messages.warning(request, f"{failed['name']}: {failed['reason']}")

            return redirect('student_exam', olympiad_id=self.olympiad.id)

        # Form буруу бол
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Файл хуулахад алдаа гарлаа. Шалтгааныг шалгана уу.'
                }, status=400)
            else:
                messages.error(request, 'Файл хуулахад алдаа гарлаа. Шалтгааныг шалгана уу.')
                context = self.get_context_data(**kwargs)
                context['form'] = form
                return render(request, self.template_name, context)



class StudentSupplementView(LoginRequiredMixin, TemplateView):
    """Нэмэлт материал илгээх view"""
    template_name = 'olympiad/supplement_exam.html'

    def dispatch(self, request, *args, **kwargs):
        olympiad_id = kwargs.get('olympiad_id')
        self.olympiad = get_object_or_404(Olympiad, pk=olympiad_id)

        access_denied = self.check_access()
        if access_denied:
            return access_denied

        return super().dispatch(request, *args, **kwargs)

    def check_access(self):
        if not self.olympiad.is_grading:
            return render(self.request, 'error.html', {
                'message': 'Нэмэлт материал хүлээн авах хугацаа дууссан.'
            })

        if self.olympiad.group:
            if self.request.user not in self.olympiad.group.user_set.all():
                messages.info(self.request, f"Зөвхөн '{self.olympiad.group.name}' бүлгийн сурагчид оролцох боломжтой")
                return redirect('olympiad_supplement_home')

        if not self.request.user.is_staff:
            results = self.olympiad.result_set.filter(contestant=self.request.user)
            if not results.exists():
                return render(self.request, 'error.html', {
                    'message': 'Зөвхөн энэ олимпиадад оролцсон сурагчид материал нэмж оруулах боломжтой.'
                })
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.ensure_results_exist()

        context['results'] = Result.objects.filter(
            contestant=self.request.user,
            olympiad=self.olympiad
        ).select_related('problem').order_by('problem__order')

        context['olympiad'] = self.olympiad
        context['contestant'] = self.request.user
        return context

    def ensure_results_exist(self):
        user = self.request.user
        problems = self.olympiad.problem_set.all().order_by('order')
        for problem in problems:
            Result.objects.get_or_create(contestant=user, olympiad=self.olympiad, problem=problem)

    # ✅ ✅ ✅  ШИНЭЧЛЭГДСЭН АЖАХ POST
    def post(self, request, *args, **kwargs):
        form = UploadForm(request.POST, request.FILES)

        if form.is_valid():
            files = request.FILES.getlist('file')

            if not files:
                return self._ajax_or_normal_error(
                    request,
                    'Зураг сонгоно уу.'
                )

            result_id = request.POST.get('result')
            uploaded_files = []
            failed_files = []

            ALLOWED_EXT = ['jpg', 'jpeg', 'png', 'gif', 'webp']
            MAX_SIZE = 10 * 1024 * 1024

            for file in files:
                ext = file.name.split('.')[-1].lower()

                if ext not in ALLOWED_EXT:
                    failed_files.append({
                        'name': file.name,
                        'reason': f'Зөвхөн {", ".join(ALLOWED_EXT)} файл хүлээн авна.'
                    })
                    continue

                if file.size > MAX_SIZE:
                    failed_files.append({
                        'name': file.name,
                        'reason': f'Хэмжээ 10MB-аас хэтэрсэн: {file.size / 1024 / 1024:.1f}MB'
                    })
                    continue

                try:
                    upload = Upload(
                        file=file,
                        result_id=result_id,
                        is_accepted=False,      # ⏳ supplement → шалгаж байна
                        is_supplement=True
                    )
                    upload.save()
                    uploaded_files.append({
                        'name': file.name,
                        'url': upload.file.url,
                        'id': upload.id
                    })
                except Exception as e:
                    failed_files.append({
                        'name': file.name,
                        'reason': f'Хадгалахад алдаа гарлаа: {e}'
                    })

            if uploaded_files:
                Result.objects.filter(pk=result_id).update(state=3)

            message = self._make_message(uploaded_files, failed_files)
            success = bool(uploaded_files)

            # ✅ AJAX → JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': success,
                    'message': message,
                    'uploaded_files': uploaded_files,
                    'failed_files': failed_files
                })

            # ❌ FORM SUBMIT → redirect (хуучин логикууд хэвээр)
            if success:
                messages.success(request, message)
            else:
                messages.error(request, message)

            return redirect('student_supplement_view', olympiad_id=self.olympiad.id)

        # ❌ form.is_valid() FALSE
        return self._ajax_or_normal_error(
            request,
            'Файл илгээхэд алдаа гарлаа. Шалтгааныг шалгана уу.'
        )

    # === Helper functions ===
    def _make_message(self, uploaded, failed):
        if uploaded and not failed:
            return f'✅ {len(uploaded)} файлыг амжилттай илгээлээ.'
        if uploaded and failed:
            return f'⚠️ {len(uploaded)} амжилттай, {len(failed)} амжилтгүй.'
        return '❌ Бүх файл алдаатай.'

    def _ajax_or_normal_error(self, request, msg):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': msg}, status=400)
        messages.error(request, msg)
        return redirect(request.path)



class ContestEndView(LoginRequiredMixin, TemplateView):
    """Олимпиад дуусcаны мэдэгдэл"""
    template_name = 'olympiad/exam/end_note.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['olympiad'] = get_object_or_404(Olympiad, pk=kwargs['olympiad_id'])
        return context