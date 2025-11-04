from django.views import View
from django.core.files.storage import default_storage

from django.views.generic import FormView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.forms import modelformset_factory
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db import transaction

from .models import Olympiad, Result, Upload
from .forms import ResultsForm, UploadForm
from .mixins import OlympiadAccessMixin, ResultsEnsureMixin

# ----------------------------
# 0. FormSet
# ----------------------------
ResultsFormSet = modelformset_factory(Result, form=ResultsForm, extra=0)


# ----------------------------
# 1. Тест-олимпиад бөглөх (Quiz)
# ----------------------------
class StudentQuizView(LoginRequiredMixin, OlympiadAccessMixin, ResultsEnsureMixin, FormView):
    """Тест олимпиад бөглөх"""
    template_name = 'olympiad/quiz/quiz.html'
    form_class = ResultsFormSet

    def get_queryset(self):
        return Result.objects.filter(
            contestant=self.request.user,
            olympiad=self.olympiad
        ).select_related('problem').order_by('problem__order')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['queryset'] = self.get_queryset()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.get_queryset()
        context['olympiad'] = self.olympiad
        context['contestant'] = self.request.user
        return context

    def form_valid(self, form):
        # Хэрэв хаалтын дараа ирвэл таслана
        if self.olympiad.is_closed():
            messages.error(self.request, 'Хариулт авах хугацаа дууссан.')
            return redirect('olympiad_end', olympiad_id=self.olympiad.id)

        # Өөрчлөгдсөн мөрүүдийг л нэг дор шинэчилнэ
        with transaction.atomic():
            results_to_update = []
            for result_form in form:
                if result_form.has_changed():
                    result = result_form.instance
                    result.answer = result_form.cleaned_data.get('answer')
                    results_to_update.append(result)

            if results_to_update:
                Result.objects.bulk_update(results_to_update, ['answer'])

        messages.success(self.request, 'Хариултыг амжилттай хадгаллаа.')
        return render(self.request, 'olympiad/quiz/quiz_view_confirm.html', {
            'results': self.get_queryset(),
            'olympiad': self.olympiad
        })

    def form_invalid(self, form):
        messages.error(self.request, 'Хариулт хадгалахад алдаа гарлаа.')
        return super().form_invalid(form)


# ----------------------------
# 2. Уламжлалт олимпиад – үндсэн зураг upload
# ----------------------------
class StudentExamView(LoginRequiredMixin, OlympiadAccessMixin, ResultsEnsureMixin, TemplateView):
    """Уламжлалт олимпиадын үндсэн upload хуудас"""
    template_name = 'olympiad/exam/exam.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        results = Result.objects.filter(
            contestant=self.request.user,
            olympiad=self.olympiad
        ).select_related('problem').order_by('problem__order')
        context['olympiad'] = self.olympiad
        context['results'] = results
        context['contestant'] = self.request.user
        return context


# ----------------------------
# 3. Нэг бодлогод зураг илгээх (modal / partial form)
# ----------------------------
class StudentResultUploadView(LoginRequiredMixin, OlympiadAccessMixin, ResultsEnsureMixin, TemplateView):
    """Онлайн шалгалтын үед нэг бодлогод зураг хуулах"""
    template_name = 'olympiad/upload_form.html'

    ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    def get(self, request, *args, **kwargs):
        result_id = request.GET.get('result_id')
        result = get_object_or_404(Result, pk=result_id, contestant=request.user, olympiad=self.olympiad)
        form = UploadForm()
        return render(request, self.template_name, {
            'result': result,
            'form': form,
            'form_action_url': request.path,
            'is_supplement': False
        })

    def post(self, request, *args, **kwargs):
        form = UploadForm(request.POST, request.FILES)
        is_ajax = request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"

        if not form.is_valid():
            if is_ajax:
                return JsonResponse({'success': False, 'message': 'Форм буруу байна.'}, status=400)
            messages.error(request, 'Форм буруу байна.')
            return redirect(request.path)

        files = request.FILES.getlist('file')
        result_id = request.POST.get('result')
        result = get_object_or_404(Result, pk=result_id, contestant=request.user, olympiad=self.olympiad)

        uploaded = []
        failed = []

        for f in files:
            ext = f.name.split('.')[-1].lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                failed.append({'name': f.name, 'reason': f'Зөвхөн {", ".join(self.ALLOWED_EXTENSIONS)}'})
                continue
            if f.size > self.MAX_FILE_SIZE:
                failed.append({'name': f.name, 'reason': '10MB-аас бага файл оруулна уу.'})
                continue

            up = Upload.objects.create(file=f, result=result, is_accepted=True, is_supplement=False)
            uploaded.append({'name': f.name, 'url': up.file.url, 'id': up.id})

        if uploaded:
            Result.objects.filter(pk=result.pk).update(state=1)

        msg = (
            f'✅ {len(uploaded)} файлыг амжилттай илгээлээ.' if uploaded and not failed else
            f'⚠️ {len(uploaded)} амжилттай, {len(failed)} амжилтгүй.' if uploaded else
            '❌ Бүх файл алдаатай.'
        )

        if is_ajax:
            return JsonResponse({
                'success': bool(uploaded),
                'message': msg,
                'uploaded_files': uploaded,
                'failed_files': failed
            }, status=200 if uploaded else 400)

        (messages.success if uploaded else messages.error)(request, msg)
        for it in failed:
            messages.warning(request, f"{it['name']}: {it['reason']}")
        return redirect('student_exam', olympiad_id=self.olympiad.id)


# ----------------------------
# 4. Supplement upload (зөвхөн grading үед нээлттэй)
# ----------------------------
class StudentSupplementView(OlympiadAccessMixin, LoginRequiredMixin, ResultsEnsureMixin, TemplateView):
    """
    Нэмэлт зураг хуулах (supplement).
    Зөвхөн олимпиад is_grading == True үед upload хийхийг зөвшөөрнө.
    Upload бүр анхнаасаа is_accepted=False, is_supplement=True төлөвтэй байна.
    """
    template_name = 'olympiad/exam/supplement_exam.html'

    ALLOWED_EXT = ['jpg', 'jpeg', 'png', 'gif', 'webp']
    MAX_SIZE = 10 * 1024 * 1024  # 10MB

    # 🔽 [ШИНЭЭР НЭМСЭН МЕТОД] 🔽
    def check_access(self):
        """
        OlympiadAccessMixin-ийн check_access-г дарж бичнэ.
        Энэ view 'is_finished'-г шалгахгүй, харин 'is_grading' эсэхийг шалгана.
        """
        user = self.request.user
        olympiad = self.olympiad  # Эцэг mixin-ийн dispatch үүнийг оноосон

        # 1. Групп шалгах
        if olympiad.group and user not in olympiad.group.user_set.all():
            messages.info(
                self.request,
                f"Зөвхөн '{olympiad.group.name}' бүлгийн сурагчид оролцох боломжтой"
            )
            return redirect('olympiad_home')

        # 2. Эхэлсэн эсэхийг шалгах (Заавал эхэлсэн байх ёстой)
        if not olympiad.is_started():
            messages.info(self.request, 'Олимпиад эхлээгүй байна.')
            return redirect('olympiad_home')

        # 3. ⛔️ 'is_finished' шалгалтыг энд хийхгүй.

        # 4. ✅ 'is_grading' шалгалтыг НЭМНЭ.
        if not olympiad.is_grading:
            messages.error(self.request, 'Энэ олимпиад нэмэлт материал хүлээж авах горимд ороогүй байна.')
            return redirect('olympiad_home')

        return None  # Бүх шалгалт давсан бол None буцаана
    # 🔼 [ШИНЭЭР НЭМСЭН МЕТОД] 🔼

    # ⛔️ АЛДААТАЙ DISPATCH МЕТОДЫГ ЭНДЭЭС УСТГАСАН ⛔️

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        results = Result.objects.filter(
            contestant=self.request.user,
            olympiad=self.olympiad
        ).select_related('problem').order_by('problem__order')
        context['olympiad'] = self.olympiad
        context['results'] = results
        return context

    def post(self, request, *args, **kwargs):
        # AJAX эсэхийг шалгах илүү найдвартай хэлбэр
        is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
        files = request.FILES.getlist('file')
        result_id = request.POST.get('result') or request.POST.get('result_id')

        if not files:
            return self._ajax_or_normal_error(request, 'Зураг сонгоно уу.', is_ajax)
        if not result_id:
            return self._ajax_or_normal_error(request, 'Result ID олдсонгүй.', is_ajax)

        uploaded_files, failed_files = [], []

        for f in files:
            ext = f.name.split('.')[-1].lower()
            if ext not in self.ALLOWED_EXT:
                failed_files.append({'name': f.name, 'reason': f'Зөвхөн {", ".join(self.ALLOWED_EXT)} өргөтгөлтэй файл зөвшөөрөгдөнө.'})
                continue
            if f.size > self.MAX_SIZE:
                failed_files.append({'name': f.name, 'reason': '10MB-аас их хэмжээтэй байна.'})
                continue

            try:
                up = Upload.objects.create(
                    file=f,
                    result_id=result_id,
                    is_accepted=False,   # ⛔ баталгаажаагүй
                    is_supplement=True   # 📎 нэмэлт материал
                )
                uploaded_files.append({'name': f.name, 'url': up.file.url, 'id': up.id})
            except Exception as e:
                failed_files.append({'name': f.name, 'reason': f'Хадгалахад алдаа гарлаа: {e}'})

        if uploaded_files:
            Result.objects.filter(pk=result_id).update(state=3)

        message = (
            f'✅ {len(uploaded_files)} файлыг амжилттай илгээлээ.' if uploaded_files and not failed_files else
            f'⚠️ {len(uploaded_files)} амжилттай, {len(failed_files)} амжилтгүй.' if uploaded_files else
            '❌ Бүх файл алдаатай.'
        )
        success = bool(uploaded_files)

        if is_ajax:
            return JsonResponse({
                'success': success,
                'message': message,
                'uploaded_files': uploaded_files,
                'failed_files': failed_files
            }, status=200 if success else 400)

        (messages.success if success else messages.error)(request, message)
        for it in failed_files:
            messages.warning(request, f"{it['name']}: {it['reason']}")

        # ⚙️ [ЗАСВАРЛАСАН ХЭСЭГ] URL name нь 'student_supplement_view' гэдэг нь тодорхой болсон.
        return redirect('student_supplement_view', olympiad_id=self.olympiad.id)


    def _ajax_or_normal_error(self, request, msg, is_ajax):
        if is_ajax:
            return JsonResponse({'success': False, 'message': msg}, status=400)
        messages.error(request, msg)
        return redirect(request.path)



# ----------------------------
# 5. Олимпиад дууссан хуудас
# ----------------------------
class ContestEndView(LoginRequiredMixin, TemplateView):
    template_name = 'olympiad/exam/end_note.html'

    def dispatch(self, request, *args, **kwargs):
        olympiad_id = kwargs.get('olympiad_id')
        self.olympiad = get_object_or_404(Olympiad, pk=olympiad_id)

        return super().dispatch(request, *args, **kwargs)


# ----------------------------
# 6. Өөрийн upload-уудыг харах
# ----------------------------
class OlympiadResultViewerView(LoginRequiredMixin, TemplateView):
    """Өөрийн оруулсан үндсэн зурагнуудыг харах viewer"""
    template_name = 'olympiad/exam/result_viewer.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result_id = self.request.GET.get('result_id')
        result = get_object_or_404(Result, pk=result_id, contestant=self.request.user)
        context['result'] = result
        context['uploads'] = result.get_uploads()
        return context


class UploadAPI(View):
    def post(self, request, *args, **kwargs):
        result_id = request.POST.get('result_id')

        # ✅ Dropzone-д paramName="file" → бүх файл request.FILES.values() дотор байна
        files = request.FILES.getlist('file') or request.FILES.getlist('file[]') or list(request.FILES.values())

        if not result_id:
            return JsonResponse({'success': False, 'message': 'result_id дутуу байна'}, status=400)
        if not files:
            return JsonResponse({'success': False, 'message': 'Файл илгээгээгүй байна'}, status=400)

        result = Result.objects.filter(id=result_id, contestant=request.user).first()
        if not result:
            return JsonResponse({'success': False, 'message': 'Result олдсонгүй'}, status=44)

        uploaded, failed = [], []

        for file in files:
            try:
                upload = Upload.objects.create(
                    result=result,
                    file=file,
                    is_accepted=True,
                    is_supplement=False
                )
                uploaded.append({
                    'id': upload.id,
                    'url': upload.file.url,
                    'name': upload.file.name
                })
            except Exception as e:
                failed.append({'name': file.name, 'reason': str(e)})

        if uploaded:
            Result.objects.filter(pk=result_id).update(state=1)

        return JsonResponse({
            'success': len(uploaded) > 0,
            'uploaded': uploaded,
            'failed': failed
        })



class DeleteUploadAPI(View):
    """AJAX delete uploaded file"""

    def delete(self, request, upload_id, *args, **kwargs):
        upload = Upload.objects.filter(id=upload_id, result__contestant=request.user).first()
        if not upload:
            return JsonResponse({'success': False, 'message': 'Файл олдсонгүй'}, status=404)

        file_path = upload.file.path
        upload.delete()

        # Physically remove file
        try:
            default_storage.delete(file_path)
        except:
            pass

        return JsonResponse({'success': True, 'deleted_id': upload_id})


class UploadedListView(TemplateView):
    template_name = "olympiad/exam/uploaded_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        result_id = self.kwargs['result_id']
        ctx["result"] = Result.objects.get(id=result_id)
        return ctx


# ⛔️ [SupplementUploadAPI КЛАССЫГ ЭНДЭЭС УСТГАСАН] ⛔️


# ⛔️ [SupplementExamView КЛАССЫГ ЭНДЭЭС УСТГАСАН] ⛔️


class SupplementListView(TemplateView):
    template_name = "olympiad/exam/supplement_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        result_id = self.kwargs['result_id']
        ctx['result'] = Result.objects.get(id=result_id)
        return ctx