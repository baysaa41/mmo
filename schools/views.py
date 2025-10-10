from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, Q
from django.core.mail import send_mail
from .email_service import SchoolEmailService
import random
import string
from django.urls import reverse

import numpy as np
import logging
# Logger үүсгэх
logger = logging.getLogger(__name__)

# Шаардлагатай import-ууд
import io
import re
from django.http import HttpResponse
from datetime import date
from openpyxl.styles import Border, Side, Font, Alignment

from .models import School
from .forms import UserSearchForm, AddUserForm, UserForm, UserMetaForm, UploadExcelForm
from accounts.models import UserMeta, Level, Province
from olympiad.models import Olympiad, SchoolYear, Problem, Result

import pandas as pd
from django.db import transaction
from .forms import UploadExcelForm

from django.contrib.admin.views.decorators import staff_member_required
from .forms import SchoolModeratorChangeForm, EditSchoolInfoForm

@login_required
def school_moderators_view(request):
    """
    Shows a list of schools. Regular moderators see their own.
    Staff users see both their own moderated schools and a separate list of all other schools.
    """
    pid = request.GET.get('p')
    zid = request.GET.get('z')
    context = {}

    if request.user.is_staff:
        # Staff хэрэглэгчийн хувьд
        # 1. Өөрийн удирддаг сургууль
        my_schools = request.user.moderating.select_related('user__data', 'group', 'province').order_by('province__name', 'name')
        context['my_schools'] = my_schools

        # 2. Бусад бүх сургууль (өөрийнхийг хассан)
        other_schools_qs = School.objects.select_related('user__data', 'group', 'province').exclude(pk__in=my_schools.values_list('pk', flat=True))

        if pid:
            other_schools_qs = other_schools_qs.filter(province_id=pid)
        elif zid:
            other_schools_qs = other_schools_qs.filter(province__zone_id=zid)

        context['other_schools'] = other_schools_qs.order_by('province__name', 'name')

    else:
        # Энгийн модераторын хувьд (хуучин логик хэвээрээ)
        schools_qs = request.user.moderating.select_related('user__data', 'group', 'province')
        if pid:
            schools_qs = schools_qs.filter(province_id=pid)
        elif zid:
            schools_qs = schools_qs.filter(province__zone_id=zid)

        final_schools = schools_qs.order_by('province__name', 'name')
        context['schools'] = final_schools

    return render(request, 'schools/moderator_school_list.html', context)

@login_required
def school_dashboard(request, school_id):
    """
    Сургуулийн удирдлагын самбар. Сурагчдын тоо болон боломжит
    олимпиадуудын жагсаалтыг харуулна.
    """
    school = get_object_or_404(School, id=school_id)
    if not request.user.is_staff and school not in request.user.moderating.all():
        messages.error(request, 'Та энэ сургуулийг удирдах эрхгүй.')
        return render(request, 'error.html', {'message': 'Хандах эрхгүй.'})

    # Сурагчдын тоог ангиллаар гаргах
    student_counts = Level.objects.annotate(
        student_count=Count('usermeta__user', filter=Q(usermeta__user__groups=school.group))
    ).order_by('name')

    uncategorized_count = school.group.user_set.filter(data__level__isnull=True).count()

    # Одоогийн хичээлийн жилийн, 1-р давааны тестүүдийг шүүх
    today = date.today()
    current_school_year = SchoolYear.objects.filter(start__lte=today, end__gte=today).first()

    olympiads = Olympiad.objects.none()
    if current_school_year:
        olympiads = Olympiad.objects.filter(
            round=1,
            school_year=current_school_year
        ).order_by('level__name')

    # --- ШИНЭЭР НЭМЭГДСЭН ЛОГИК ---
    # Тухайн сургуулийг сонгосон боловч группт нь ороогүй сурагчдыг олох
    pending_students = User.objects.filter(
        data__school=school
    ).exclude(
        groups=school.group
    )

    context = {
        'school': school,
        'student_counts_by_level': student_counts,
        'uncategorized_count': uncategorized_count,
        'pending_students': pending_students, # <-- context-д нэмэх
        'olympiads': olympiads,
    }
    return render(request, 'schools/school_dashboard.html', context)

@login_required
def manage_school_by_level(request, school_id, level_id):
    """
    Сонгогдсон нэг ангиллын (эсвэл ангилалгүй) сурагчдыг удирдах хуудас.
    """
    school = get_object_or_404(School, id=school_id)
    if not request.user.is_staff and school not in request.user.moderating.all():
        messages.error(request, 'Та энэ сургуулийг удирдах эрхгүй.')
        return render(request, 'error.html', {'message': 'Хандах эрхгүй.'})

    group = school.group

    # --- ШИНЭЧИЛСЭН ЛОГИК ---
    if level_id == 100: # 100 нь "Бүх сурагчид" гэсэн утгатай
        selected_level = {'id': 100, 'name': 'Бүх сурагчид'}
        users_in_level = group.user_set.all().select_related('data__grade')
    elif level_id == 0:
        selected_level = {'id': 0, 'name': 'Ангилалгүй'}
        users_in_level = group.user_set.filter(data__level__isnull=True).select_related('data__grade')
    else:
        selected_level = get_object_or_404(Level, id=level_id)
        users_in_level = group.user_set.filter(data__level=selected_level).select_related('data__grade')

    search_results = None
    if request.method == 'POST':
        if 'search_users' in request.POST:
            search_form = UserSearchForm(request.POST)
            add_user_form = AddUserForm()
            if search_form.is_valid():
                search_results = search_form.search_users()

        elif 'add_user' in request.POST:
            add_user_form = AddUserForm(request.POST)
            search_form = UserSearchForm()
            if add_user_form.is_valid():
                new_user = None
                try:
                    with transaction.atomic():
                        new_user = add_user_form.save(commit=False)
                        new_user.username = ''.join(random.choice(string.ascii_letters) for _ in range(32))
                        temp_password = User.objects.make_random_password(length=20)
                        new_user.set_password(temp_password)
                        new_user.save()
                        new_user.username = f'u{new_user.id}'
                        new_user.save()

                        meta_data = {
                            'user': new_user,
                            'school': request.user.data.school,
                            'province': request.user.data.province,
                        }
                        if level_id != 0:
                            meta_data['level'] = selected_level

                        if level_id == 100:
                            selected_level = Level.objects.get(pk=8)
                            meta_data['level'] = selected_level

                        UserMeta.objects.create(**meta_data)
                        new_user.groups.add(group)

                    # Тавтай морилно уу имэйл + password reset link илгээх
                    school_name = request.user.data.school.name if request.user.data.school else "ММОХ"
                    success, error = SchoolEmailService.send_new_user_welcome_with_reset_link(
                        new_user,
                        school_name,
                        request
                    )

                    level_name = selected_level['name'] if level_id == 0 else selected_level.name

                    if success:
                        messages.success(
                            request,
                            f"'{new_user.get_full_name()}' хэрэглэгчийг '{level_name}' хэсэгт "
                            f"амжилттай нэмж, нэвтрэх мэдээллийг и-мэйлээр илгээлээ."
                        )
                    else:
                        messages.warning(
                            request,
                            f"Хэрэглэгч үүссэн ч и-мэйл илгээхэд алдаа гарлаа. "
                            f"Та дахин илгээх эсвэл password reset хийлгэнэ үү."
                        )

                except Exception as e:
                    messages.error(request, f"Хэрэглэгч үүсгэхэд алдаа гарлаа: {e}")
                    logger.error(f"User creation failed: {e}", exc_info=True)

                return redirect('manage_school_by_level', school_id=school_id, level_id=level_id)

        elif 'add_existing_user' in request.POST:
            search_form = UserSearchForm()
            add_user_form = AddUserForm()
            user_id = request.POST.get('user_id')
            user_to_add = get_object_or_404(User, id=user_id)

            user_meta = getattr(user_to_add, "data", None)

            if not user_meta:
                messages.error(request, "Энэ хэрэглэгчид профайл (UserMeta) бүртгэл алга байна.")
                return redirect('manage_school_by_level', school_id=school_id, level_id=level_id)

            # зөвхөн staff л staff-ийг нэмэх эрхтэй
            if not request.user.is_staff and user_to_add.is_staff:
                messages.error(request, "Танд энэ хэрэглэгчийг нэмэх эрх байхгүй.")
                return redirect('manage_school_by_level', school_id=school_id, level_id=level_id)

            # админыг нэмж болохгүй
            if user_to_add.is_superuser:
                messages.error(request, "Танд энэ хэрэглэгчийг нэмэх эрх байхгүй.")
                return redirect('manage_school_by_level', school_id=school_id, level_id=level_id)

            # Хуучин сургууль нь өөр байвал зөвхөн staff эрхтэй хүн сольж чадна
            if user_meta.school and user_meta.school != school and not request.user.is_staff:
                messages.error(
                    request,
                    f"'{user_to_add.get_full_name()}' хэрэглэгч '{user_meta.school.name}' сургуульд бүртгэлтэй тул нэмэх боломжгүй. "
                    f"Зөвхөн системийн админ шилжүүлэг хийж чадна."
                )
            else:
                # Хуучин сургуульд байсан group-оос хасах (staff үед)
                if request.user.is_staff and user_meta.school and user_meta.school != school:
                    old_group = user_meta.school.group
                    if old_group:
                        old_group.user_set.remove(user_to_add)

                # Шинэ сургуульд оноох
                user_meta.school = school
                if level_id != 0:
                    user_meta.level = selected_level if isinstance(selected_level, Level) else None
                user_meta.save()

                group.user_set.add(user_to_add)
                messages.success(
                    request,
                    f"'{user_to_add.get_full_name() or user_to_add.username}' хэрэглэгчийг '{school.name}' сургуульд амжилттай нэмлээ."
                )

            if user_to_add.data.level_id != level_id:
                level_id = 100

            return redirect('manage_school_by_level', school_id=school_id, level_id=level_id)

        elif 'remove_user' in request.POST:
            search_form = UserSearchForm()
            add_user_form = AddUserForm()
            user_id = request.POST.get('user_id')
            user_to_remove = get_object_or_404(User, id=user_id)
            group.user_set.remove(user_to_remove)
            messages.info(request, f"'{user_to_remove.get_full_name() or user_to_remove.username}' хэрэглэгчийг сургуулиас хаслаа.")
            return redirect('manage_school_by_level', school_id=school_id, level_id=level_id)

    else: # GET request
        search_form = UserSearchForm()
        add_user_form = AddUserForm()

    context = {
        'school': school,
        'group': group,
        'selected_level': selected_level,
        'users_in_level': users_in_level,
        'search_form': search_form,
        'add_user_form': add_user_form,
        'search_results': search_results,
    }
    return render(request, 'schools/manage_school_users_level.html', context)

@login_required
def school_level_olympiad_view(request, school_id, level_id, olympiad_id):
    school = get_object_or_404(School, id=school_id)
    olympiad = get_object_or_404(Olympiad, id=olympiad_id)

    if level_id == 0:
        selected_level = {'id': 0, 'name': 'Ангилалгүй'}
    else:
        selected_level = get_object_or_404(Level, id=level_id)

    upload_form = UploadExcelForm()
    context = {
        'school': school,
        'olympiad': olympiad,
        'selected_level': selected_level,
        'upload_form': upload_form,
    }
    return render(request, 'schools/school_level_olympiad_detail.html', context)


@login_required
def generate_school_answer_sheet(request, school_id, olympiad_id):
    """Сонгосон сургууль, олимпиадын хариултын хуудсыг үүсгэж, шууд download хийлгэнэ."""
    school = get_object_or_404(School, pk=school_id)
    olympiad = get_object_or_404(Olympiad, pk=olympiad_id)

    # Эрхийн шалгалт
    if not request.user.is_staff and school not in request.user.moderating.all():
        messages.error(request, 'Та энэ үйлдлийг хийх эрхгүй.')
        return redirect('school_dashboard', school_id=school_id)

    # Дата бэлдэх
    level = olympiad.level
    contestants = User.objects.filter(groups=school.group, data__level=level).order_by('last_name', 'first_name')
    problems = olympiad.problem_set.all().order_by('order')

    # 1-р Sheet: Хариулт
    answers_data = []
    for c in contestants:
        answers_data.append({
            'ID': c.id,
            'Овог': c.last_name,
            'Нэр': c.first_name,
            **{f'№{p.order}': '' for p in problems}
        })
    header = ['ID', 'Овог', 'Нэр'] + [f'№{p.order}' for p in problems]
    answers_df = pd.DataFrame(answers_data, columns=header)

    # 2-р Sheet: Мэдээлэл
    info_data = {
        'Түлхүүр': ['olympiad_id', 'olympiad_name', 'school_id', 'school_name', 'level_id', 'level_name'],
        'Утга': [olympiad.id, olympiad.name, school.id, school.name, level.id, level.name]
    }
    info_df = pd.DataFrame(info_data)

    # Excel файлыг санах ойд үүсгэх
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        answers_df.to_excel(writer, sheet_name='Хариулт', index=False)
        info_df.to_excel(writer, sheet_name='Мэдээлэл', index=False)

        # Style-г тохируулах workbook болон worksheet-г авах
        workbook = writer.book
        worksheet = writer.sheets['Хариулт']

        # Style-уудыг тодорхойлох
        thin_border = Border(left=Side(style='thin'),
                             right=Side(style='thin'),
                             top=Side(style='thin'),
                             bottom=Side(style='thin'))
        bold_font = Font(bold=True)
        center_align = Alignment(horizontal='center', vertical='center')

        # Header буюу эхний мөрийг загварчлах
        for cell in worksheet["1:1"]:
            cell.font = bold_font
            cell.border = thin_border
            cell.alignment = center_align

        # Үндсэн өгөгдлийн нүднүүдэд хүрээ нэмэх
        for row in worksheet.iter_rows(min_row=2,
                                       max_row=worksheet.max_row,
                                       max_col=worksheet.max_column):
            for cell in row:
                cell.border = thin_border

        # Баганын өргөнийг тохируулах
        for i, column_cells in enumerate(worksheet.columns):
            column_letter = column_cells[0].column_letter
            if i < 3: # ID, Овог, Нэр баганууд
                length = max(len(str(cell.value)) for cell in column_cells)
                worksheet.column_dimensions[column_letter].width = length + 2
            else: # Хариултын баганууд
                worksheet.column_dimensions[column_letter].width = 5

    output.seek(0)

    # Хэрэглэгчид файл болгож буцаах
    filename = f"answer_sheet_{olympiad.id}_{school.id}.xlsx"
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

# schools/views.py файлын дээд хэсэгт "time" модулийг импортлоно
import time
# ... (бусад import-ууд хэвээрээ) ...

@login_required
def import_school_answer_sheet(request, school_id, olympiad_id):
    """Excel-ээс бөглөсөн хариултын хуудсыг уншиж, Result руу импортлоно."""
    school = get_object_or_404(School, pk=school_id)
    olympiad = get_object_or_404(Olympiad, pk=olympiad_id)
    level_id = olympiad.level_id

    # Эрхийн шалгалт
    if not request.user.is_staff and school not in request.user.moderating.all():
        messages.error(request, "Та энэ үйлдлийг хийх эрхгүй.")
        return redirect('school_dashboard', school_id=school_id)

    if request.method == 'POST':
        form = UploadExcelForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_excel = form.save(commit=False)
            uploaded_excel.uploaded_by = request.user
            uploaded_excel.save()
            excel_file = uploaded_excel.file.path

            # --- Хугацаа хэмжиж эхлэх ---
            start_time = time.time()

            try:
                # --- МЭДЭЭЛЭЛ sheet унших ---
                df_info = pd.read_excel(excel_file, sheet_name='Мэдээлэл')
                info_dict = pd.Series(df_info.Утга.values, index=df_info.Түлхүүр).to_dict()

                # Зөв сургууль, зөв олимпиад эсэхийг шалгах
                if int(info_dict.get('olympiad_id')) != olympiad.id or int(info_dict.get('school_id')) != school.id:
                    messages.error(request, "Файл өөр олимпиад/сургуульд зориулагдсан байна.")
                    return redirect('school_level_olympiad_view', school_id=school_id, level_id=level_id, olympiad_id=olympiad_id)

                # --- Хариулт sheet унших ---
                df = pd.read_excel(excel_file, sheet_name='Хариулт')
                problems_map = {p.order: p for p in Problem.objects.filter(olympiad=olympiad)}

                if 'ID' not in df.columns:
                    messages.error(request, "Excel-ийн 'Хариулт' sheet-д 'ID' багана байхгүй байна.")
                    return redirect('school_dashboard', school_id=school_id)

                updated_count = created_count = skipped_rows = invalid_format_count = 0

                for index, row in df.iterrows():
                    user_id = row.get('ID')
                    if pd.isna(user_id):
                        skipped_rows += 1
                        continue

                    try:
                        user = User.objects.get(pk=int(user_id))
                    except (User.DoesNotExist, ValueError, TypeError):
                        skipped_rows += 1
                        continue

                    # Сурагч зөв сургуулийн group-д багтсан эсэх
                    if not user.groups.filter(pk=school.group.id).exists():
                        skipped_rows += 1
                        continue

                    with transaction.atomic():
                        for order, problem in problems_map.items():
                            col = f'№{order}'
                            if col not in df.columns:
                                continue

                            answer = row[col]
                            db_value = None
                            valid = False

                            if pd.notna(answer) and str(answer).strip() != '':
                                try:
                                    fa = float(answer)
                                    if fa > 0 and fa.is_integer():
                                        db_value = int(fa)
                                        valid = True
                                except (ValueError, TypeError):
                                    pass

                            if not valid and pd.notna(answer) and str(answer).strip() != '':
                                invalid_format_count += 1

                            obj, created = Result.objects.update_or_create(
                                contestant=user, olympiad=olympiad, problem=problem,
                                defaults={'answer': db_value}
                            )
                            if created:
                                created_count += 1
                            else:
                                updated_count += 1


                # --- Хугацаа хэмжиж дуусгах ---
                elapsed_time = round(time.time() - start_time, 2)

                messages.success(
                    request,
                    f"Excel боловсрууллаа ({elapsed_time} секунд). "
                    f"Үүссэн: {created_count}, "
                    f"Шинэчлэгдсэн: {updated_count}, "
                    f"Буруу форматтай: {invalid_format_count}, "
                    f"Алгассан: {skipped_rows}."
                )

            except Exception as e:
                messages.error(request, f"Файл боловсруулахад алдаа: {e}")
                return redirect('school_dashboard', school_id=school_id)

            # Амжилтын дараа дүнгийн хуудас руу шилжих
            target_url = reverse('olympiad_answer_view', args=[olympiad_id])
            final_url = f"{target_url}?s={school_id}&p={school.province.id}"
            return redirect(final_url)

        else:
            messages.error(request, "Файл хуулахад алдаа гарлаа.")

    return redirect('school_dashboard', school_id=school_id)


@login_required
def view_school_olympiad_results(request, school_id, olympiad_id):
    """
    Сонгосон сургууль, олимпиадын хувьд сурагчдын авсан оноог харуулна.
    Энэ хувилбарт аймгийн шүүлтүүр хасагдаж, нийт онооны багана нэмэгдсэн.
    """
    sid = school_id
    context_data = ''

    try:
        # Олимпиад болон сургуулийн мэдээллийг татах
        olympiad = Olympiad.objects.get(pk=olympiad_id)
        school = School.objects.get(pk=sid)
    except (Olympiad.DoesNotExist, School.DoesNotExist):
        return render(request, 'olympiad/results/no_olympiad.html', {'message': 'Олимпиад эсвэл сургууль олдсонгүй.'})

    # Тухайн олимпиад, сургуульд хамаарах бүх дүнг татах
    results = Result.objects.filter(olympiad_id=olympiad_id, contestant__data__school_id=sid)

    if results.exists():
        # Дүнгүүдээс pandas DataFrame үүсгэх (хариултын оронд оноог ашиглана)
        rows = list(results.values_list('contestant_id', 'problem_id', 'score'))
        data = pd.DataFrame(rows, columns=['contestant_id', 'problem_id', 'score'])

        # Хүснэгтийг эргүүлж, сурагчдыг мөр, бодлогуудыг багана болгох
        # Хэрэв тухайн бодлогод оноо аваагүй бол 0 гэж тооцно
        results_df = pd.pivot_table(data, index='contestant_id', columns='problem_id', values='score', aggfunc='sum', fill_value=0)

        # Баганын нэрийг бодлогын дугаараар солих
        problem_ids = results_df.columns.values
        problem_orders = {p.id: f'№{p.order}' for p in Problem.objects.filter(id__in=problem_ids)}
        results_df.columns = [problem_orders.get(col, 'Unknown') for col in results_df.columns]

        # "Нийт" онооны багана нэмэх
        results_df['Нийт'] = results_df.sum(axis=1)

        # Багануудыг эрэмбэлэх (Бодлогууд -> Нийт)
        problem_cols = sorted([col for col in results_df.columns if col != 'Нийт'])
        results_df = results_df[problem_cols + ['Нийт']]

        # Сурагчдын мэдээллийг авах
        contestant_ids = list(results_df.index)
        contestants_data = User.objects.filter(pk__in=contestant_ids).values('id', 'last_name', 'first_name')
        user_df = pd.DataFrame(list(contestants_data))
        user_df.columns = ['ID', 'Овог', 'Нэр']

        # Сурагчдын мэдээллийг онооны хүснэгттэй нэгтгэх
        user_results_df = pd.merge(user_df, results_df, left_on='ID', right_index=True, how='left')

        # Нийт оноогоор буурахаар, дараа нь нэрээр өсөхөөр эрэмбэлэх
        sorted_df = user_results_df.sort_values(
            by=['Нийт', 'Овог', 'Нэр'],
            ascending=[False, True, True]
        ).drop(columns=['ID'])

        # Индексийг 1-ээс эхлүүлэх
        sorted_df.index = np.arange(1, len(sorted_df) + 1)

        # Онооны багануудыг тодорхойлох
        numeric_columns = [col for col in sorted_df.columns if str(col).startswith('№') or str(col) == 'Нийт']

        # Оноог нэг орны нарийвчлалтай форматлах
        formatter = '{:.1f}'.format

        # HTML гаргалт руу хөрвүүлэхдээ style тохируулах
        styled_df = (sorted_df.style
                              .format(formatter, subset=numeric_columns, na_rep="-")
                              .set_table_attributes('class="table table-bordered table-hover"'))
        context_data = styled_df.to_html()

    # Template-д дамжуулах мэдээллийг бэлтгэх
    title = f"{school.name} - {olympiad.name}"
    name = f"{olympiad.name}, {olympiad.level.name} ангилал"

    context = {
        'title': f"{title} - Дүн",
        'name': name,
        'data': context_data,
        'school': school,
        'selected_sid': sid,
        'olympiad_id': olympiad_id,
    }

    return render(request, 'olympiad/results/school_results.html', context)

@login_required
def edit_user_in_group(request, user_id):
    """
    Handles editing a student's profile information by a school moderator.
    """
    target_user = get_object_or_404(User, id=user_id)

    if request.user.is_staff:
        school = School.objects.filter(group__user=target_user).first()
    else:
        school = School.objects.filter(group__user=target_user, user=request.user).first()
        if not school:
            messages.error(request, 'Та энэ хэрэглэгчийг засах эрхгүй.')
            return render(request, 'error.html', {'message': 'Хандах эрхгүй.'})

    user_meta = get_object_or_404(UserMeta, user=target_user)

    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=target_user)
        user_meta_form = UserMetaForm(request.POST, request.FILES, instance=user_meta)

        if user_form.is_valid() and user_meta_form.is_valid():
            user_form.save()
            user_meta_form.save()
            messages.success(request, 'Профайлыг амжилттай шинэчиллээ!')
            return redirect('edit_user_in_group', user_id=user_id)
        else:
            messages.error(request, 'Доорх алдааг засна уу.')
    else:
        user_form = UserForm(instance=target_user)
        user_meta_form = UserMetaForm(instance=user_meta)

    context = {
        'user_form': user_form,
        'user_meta_form': user_meta_form,
        'target_user': target_user,
        'school': school,
        'level': user_meta.level,
    }
    return render(request, 'schools/edit_user_in_group.html', context)

@login_required
def edit_profile(request):
    """This view is for users editing their own profile."""
    user = request.user
    user_meta, created = UserMeta.objects.get_or_create(user=user)

    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=user)
        user_meta_form = UserMetaForm(request.POST, request.FILES, instance=user_meta)
        if user_form.is_valid() and user_meta_form.is_valid():
            user_form.save()
            user_meta_form.save()
            messages.success(request, 'Таны мэдээлэл амжилттай шинэчлэгдлээ.')
            return redirect('edit_profile')
    else:
        user_form = UserForm(instance=user)
        user_meta_form = UserMetaForm(instance=user_meta)

    context = {
        'user_form': user_form,
        'user_meta_form': user_meta_form,
    }
    return render(request, 'schools/edit_profile.html', context)

@login_required
def add_student_to_group_view(request, school_id, user_id):
    school = get_object_or_404(School, id=school_id)
    student = get_object_or_404(User, id=user_id)

    # Эрхийн шалгалт
    if not request.user.is_staff and school not in request.user.moderating.all():
        messages.error(request, 'Та энэ үйлдлийг хийх эрхгүй.')
        return redirect('school_dashboard', school_id=school.id)

    # Сурагчийг сургуулийн группт нэмэх
    if school.group:
        # Шалгалт: Сурагч үнэхээр энэ сургуулийг сонгосон эсэх
        if student.data.school == school:
            school.group.user_set.add(student)
            messages.success(request, f"'{student.get_full_name()}' сурагчийг сургуулийн бүлэгт амжилттай нэмлээ.")
        else:
            messages.warning(request, f"'{student.get_full_name()}' сурагч энэ сургуулийг сонгоогүй байна.")
    else:
        messages.error(request, "Энэ сургуульд групп оноогоогүй тул сурагч нэмэх боломжгүй.")

    return redirect('school_dashboard', school_id=school.id)

# ... (import-ууд) ...
from .forms import SchoolAdminPasswordChangeForm

@login_required
def change_student_password_view(request, user_id):
    """
    Сургуулийн модератор нь сурагчийн нууц үгийг солих хуудас.
    """
    target_user = get_object_or_404(User, id=user_id)
    moderator = request.user

    # --- АЮУЛГҮЙ БАЙДЛЫН ШАЛГАЛТУУД ---
    # 1. Засварлах гэж буй хэрэглэгч нь staff/superuser биш байх ёстой.
    if (target_user.is_staff or target_user.is_superuser) and not request.user.is_superuser:
        messages.error(request, "Та staff эрхтэй хэрэглэгчийн нууц үгийг солих боломжгүй.")
        return redirect('school_dashboard', school_id=moderator.data.school.id) # Өөрийнх нь dashboard руу буцаах

    # 2. Модератор нь тухайн сурагчийн сургуульд хамааралтай эсэхийг шалгах.
    try:
        # Сурагчийн сургуулийг олох
        student_school = target_user.data.school
        # Модераторын удирддаг сургуулиудыг олох
        moderator_schools = School.objects.filter(user=moderator)

        if (not student_school or not moderator_schools.filter(pk=student_school.pk).exists()) and not request.user.is_staff:
            messages.error(request, "Та энэ сурагчийн нууц үгийг солих эрхгүй.")
            return redirect('school_dashboard', school_id=moderator.data.school.id)
    except UserMeta.DoesNotExist:
        messages.error(request, "Сурагчийн профайлын мэдээлэл олдсонгүй.")
        return redirect('school_dashboard', school_id=moderator.data.school.id)

    if request.method == 'POST':
        form = SchoolAdminPasswordChangeForm(user=target_user, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{target_user.get_full_name()}' хэрэглэгчийн нууц үгийг амжилттай солилоо.")
            # Буцах замыг зөв тодорхойлох
            return redirect('manage_school_by_level', school_id=student_school.id, level_id=target_user.data.level.id)
    else:
        form = SchoolAdminPasswordChangeForm(user=target_user)

    context = {
        'form': form,
        'target_user': target_user,
    }
    return render(request, 'schools/change_student_password.html', context)


@staff_member_required
def manage_all_schools_view(request):
    """
    Бүх сургуулийн жагсаалтыг дэлгэрэнгүй мэдээлэлтэй харуулж,
    модератор солих үйлдэл хийдэг хуудас.
    """
    if request.method == 'POST':
        school_id = request.POST.get('school_id')
        school_to_change = get_object_or_404(School, id=school_id)
        form = SchoolModeratorChangeForm(request.POST)

        if form.is_valid():
            new_moderator = form.cleaned_data['user']
            school_to_change.user = new_moderator
            school_to_change.save()
            messages.success(request, f"'{school_to_change.name}' сургуулийн модераторыг амжилттай солилоо.")
        else:
            messages.error(request, "Модератор солиход алдаа гарлаа.")

        return redirect('manage_all_schools')

    # Сургуулиудын жагсаалтыг бүх мэдээлэлтэй нь авах
    all_schools = School.objects.select_related(
        'province', 'user', 'user__data'
    ).annotate(
        student_count=Count('group__user')
    ).order_by('province__name', 'name')

        # URL-аас шүүлтүүрийн утгуудыг авах
    name_query = request.GET.get('q', '')
    province_id = request.GET.get('p', '')
    zone_id = request.GET.get('z', '')

    # Шүүлтүүрүүдийг хийх
    if name_query:
        all_schools = all_schools.filter(name__icontains=name_query)
    if province_id:
        all_schools = all_schools.filter(province_id=province_id)
    if zone_id:
        all_schools = all_schools.filter(province__zone_id=zone_id)

    # Эрэмбэлэх
    all_schools = all_schools.order_by('province__name', 'name')

    change_form = SchoolModeratorChangeForm()

    context = {
        'schools': all_schools,
        'change_form': change_form,
    }
    return render(request, 'schools/manage_all_schools.html', context)

@staff_member_required
def change_school_admin_view(request, school_id):
    """
    Сургуулийн админыг хайж олоод солих хуудас.
    """
    school = get_object_or_404(School, id=school_id)
    search_results = None

    if request.method == 'POST':
        # Хэрэв "assign_admin" үйлдэл хийгдэж байвал
        if 'assign_admin' in request.POST:
            user_id = request.POST.get('user_id')
            new_admin = get_object_or_404(User, id=user_id)
            school.user = new_admin
            school.save()
            messages.success(request, f"'{school.name}' сургуулийн админыг '{new_admin.get_full_name()}' хэрэглэгчээр амжилттай солилоо.")
            return redirect('manage_all_schools')

        # Хэрэв "search_users" үйлдэл хийгдэж байвал
        search_form = UserSearchForm(request.POST)
        if search_form.is_valid():
            search_results = search_form.search_users()

    else:
        search_form = UserSearchForm()

    context = {
        'school': school,
        'search_form': search_form,
        'search_results': search_results,
    }
    return render(request, 'schools/change_school_admin.html', context)


@staff_member_required
def edit_school_admin_view(request, user_id):
    """Сургуулийн админы профайлыг засах хуудас."""
    target_user = get_object_or_404(User, id=user_id)
    # Админ хэрэглэгчид UserMeta байхгүй бол үүсгэх
    user_meta, created = UserMeta.objects.get_or_create(user=target_user)

    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=target_user)
        user_meta_form = UserMetaForm(request.POST, request.FILES, instance=user_meta)
        if user_form.is_valid() and user_meta_form.is_valid():
            user_form.save()
            user_meta_form.save()
            messages.success(request, f"'{target_user.get_full_name()}' хэрэглэгчийн мэдээллийг амжилттай шинэчиллээ.")
            return redirect('manage_all_schools')
    else:
        user_form = UserForm(instance=target_user)
        user_meta_form = UserMetaForm(instance=user_meta)

    context = {
        'user_form': user_form,
        'user_meta_form': user_meta_form,
        'target_user': target_user,
    }
    return render(request, 'schools/edit_school_admin.html', context)


@staff_member_required
def change_school_admin_password_view(request, user_id):
    """Сургуулийн админы нууц үгийг солих хуудас."""
    target_user = get_object_or_404(User, id=user_id)

    # Аюулгүй байдлын шалгалт: staff хэрэглэгч өөр staff-ийн нууц үгийг солихыг хориглох
    if target_user.is_staff or target_user.is_superuser:
        # Өөрийнхөөс бусад staff-ийн нууц үгийг солихгүй
        if target_user != request.user:
            messages.error(request, "Та өөр staff эрхтэй хэрэглэгчийн нууц үгийг эндээс солих боломжгүй.")
            return redirect('manage_all_schools')

    if request.method == 'POST':
        form = SchoolAdminPasswordChangeForm(user=target_user, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{target_user.get_full_name()}' хэрэглэгчийн нууц үгийг амжилттай солилоо.")
            return redirect('manage_all_schools')
    else:
        form = SchoolAdminPasswordChangeForm(user=target_user)

    context = {
        'form': form,
        'target_user': target_user,
    }
    return render(request, 'schools/change_student_password.html', context) # Өмнөх template-г дахин ашиглаж болно


def school_list_view(request):
    # Textarea-аас орж ирсэн түүхий текстийг авах
    query_string = request.GET.get('q', '')

    # Орж ирсэн текстийг зай, таслал, эсвэл мөрийн төгсгөлөөр нь салгаж цэвэрлэх
    # Жишээ: "a@a.com, b@b.com\nc@c.com" -> ['a@a.com', 'b@b.com', 'c@c.com']
    emails = [email for email in re.split(r'[\s,;]+', query_string) if email]

    # Үндсэн шүүлт хийгээгүй үеийн бүх сургуулийн жагсаалт
    schools = School.objects.select_related('user', 'province').order_by('name')

    # Хэрэв имэйл хаягууд орж ирсэн бол шүүлт хийх
    if emails:
        # __in шүүлтүүр нь жагсаалтад байгаа ямар нэг утгатай таарч байвал шүүнэ
        schools = schools.filter(user__email__in=emails)

    context = {
        'schools': schools,
        'search_query': query_string,  # Хэрэглэгчийн оруулсан утгыг буцааж харуулах
    }
    return render(request, 'schools/school_list.html', context)

@staff_member_required
def edit_school_info_view(request, school_id):
    """
    Сургуулийн нэр, аймаг/дүүрэг засах болон модератор солих хоёр үйлдлийг нэг хуудсанд.
    """
    school = get_object_or_404(School, id=school_id)

    if request.method == 'POST':
        # Хэрэв сургуулийн мэдээлэл өөрчлөх form илгээгдсэн бол
        if 'save_school_info' in request.POST:
            info_form = EditSchoolInfoForm(request.POST, instance=school)
            if info_form.is_valid():
                info_form.save()
                messages.success(request, "Сургуулийн мэдээлэл амжилттай шинэчлэгдлээ.")
                return redirect('manage_all_schools')
    else:
        info_form = EditSchoolInfoForm(instance=school)
        moderator_form = SchoolModeratorChangeForm()

    return render(request, 'schools/edit_school_info.html', {
        'school': school,
        'info_form': info_form,
    })
