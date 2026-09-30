from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Level, Province, UserMeta
from schools.models import School


TEST_STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


def make_user(username, school=None, province=None, **kwargs):
    user = User.objects.create_user(username=username, password='OldPass!2345', **kwargs)
    UserMeta.objects.create(user=user, school=school, province=province)
    return user


@override_settings(
    STORAGES=TEST_STORAGES,
    MAINTENANCE_MODE=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class SchoolAccessTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.province_a = Province.objects.create(name='Аймаг А')
        cls.province_b = Province.objects.create(name='Аймаг Б')

        cls.moderator_a = make_user('mod_a', province=cls.province_a)
        cls.moderator_b = make_user('mod_b', province=cls.province_b)
        cls.school_a = School.objects.create(
            name='Сургууль А', province=cls.province_a, user=cls.moderator_a,
            group=Group.objects.create(name='School_A'),
        )
        cls.school_b = School.objects.create(
            name='Сургууль Б', province=cls.province_b, user=cls.moderator_b,
            group=Group.objects.create(name='School_B'),
        )
        cls.moderator_a.data.school = cls.school_a
        cls.moderator_a.data.save()
        cls.moderator_b.data.school = cls.school_b
        cls.moderator_b.data.save()

        cls.province_manager_b = make_user('pm_b')
        cls.province_b.contact_person = cls.province_manager_b
        cls.province_b.save()

        cls.staff = make_user('staff', is_staff=True)

        cls.student_b = make_user('student_b', school=cls.school_b, province=cls.province_b)
        cls.school_b.group.user_set.add(cls.student_b)
        cls.schoolless_student = make_user('no_school')

        cls.level = Level.objects.create(name='C (5-6)')


class SchoolListViewTests(SchoolAccessTestBase):
    def test_anonymous_cannot_see_moderator_contacts(self):
        response = self.client.get(reverse('school_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response['Location'])

    def test_non_staff_is_denied(self):
        self.client.force_login(self.moderator_a)
        response = self.client.get(reverse('school_list'))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_view(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('school_list'))
        self.assertEqual(response.status_code, 200)


class ChangeStudentPasswordTests(SchoolAccessTestBase):
    NEW_PASSWORD = {'new_password1': 'Xk29!mmoNewPass', 'new_password2': 'Xk29!mmoNewPass'}

    def post(self, target):
        return self.client.post(reverse('change_student_password', args=[target.id]), self.NEW_PASSWORD)

    def assert_password_unchanged(self, user):
        user.refresh_from_db()
        self.assertTrue(user.check_password('OldPass!2345'))

    def test_moderator_cannot_change_schoolless_user_password(self):
        self.client.force_login(self.moderator_a)
        response = self.post(self.schoolless_student)
        self.assertRedirects(response, reverse('my_managed_schools'), fetch_redirect_response=False)
        self.assert_password_unchanged(self.schoolless_student)

    def test_moderator_cannot_change_other_school_student_password(self):
        self.client.force_login(self.moderator_a)
        self.post(self.student_b)
        self.assert_password_unchanged(self.student_b)

    def test_moderator_can_change_own_school_student_password(self):
        self.client.force_login(self.moderator_b)
        response = self.post(self.student_b)
        self.assertRedirects(
            response, reverse('school_all_users', args=[self.school_b.id]), fetch_redirect_response=False
        )
        self.student_b.refresh_from_db()
        self.assertTrue(self.student_b.check_password(self.NEW_PASSWORD['new_password1']))

    def test_province_manager_can_change_student_password(self):
        self.client.force_login(self.province_manager_b)
        self.post(self.student_b)
        self.student_b.refresh_from_db()
        self.assertTrue(self.student_b.check_password(self.NEW_PASSWORD['new_password1']))

    def test_moderator_cannot_change_staff_password(self):
        self.school_a.group.user_set.add(self.staff)
        self.client.force_login(self.moderator_a)
        self.post(self.staff)
        self.assert_password_unchanged(self.staff)

    def test_user_without_usermeta_gets_no_server_error(self):
        no_meta = User.objects.create_user(username='no_meta', password='x')
        self.client.force_login(no_meta)
        response = self.post(self.student_b)
        self.assertEqual(response.status_code, 302)
        self.assert_password_unchanged(self.student_b)

    def test_user_can_change_own_password_and_stays_logged_in(self):
        self.client.force_login(self.schoolless_student)
        response = self.post(self.schoolless_student)
        self.assertRedirects(response, reverse('user_profile'), fetch_redirect_response=False)
        self.schoolless_student.refresh_from_db()
        self.assertTrue(self.schoolless_student.check_password(self.NEW_PASSWORD['new_password1']))
        self.assertEqual(self.client.get(reverse('user_profile')).status_code, 200)


class EditUserInGroupTests(SchoolAccessTestBase):
    def test_moderator_cannot_edit_other_school_student(self):
        self.client.force_login(self.moderator_a)
        response = self.client.get(reverse('edit_user_in_group', args=[self.student_b.id]))
        self.assertContains(response, 'Хандах эрхгүй')

    def test_moderator_can_edit_own_school_student(self):
        self.client.force_login(self.moderator_b)
        response = self.client.get(reverse('edit_user_in_group', args=[self.student_b.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['school'], self.school_b)

    def test_province_manager_can_edit_student(self):
        self.client.force_login(self.province_manager_b)
        response = self.client.get(reverse('edit_user_in_group', args=[self.student_b.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['school'], self.school_b)

    def test_moderator_cannot_edit_staff_in_group(self):
        self.school_b.group.user_set.add(self.staff)
        self.client.force_login(self.moderator_b)
        response = self.client.post(reverse('edit_user_in_group', args=[self.staff.id]), {
            'last_name': 'X', 'first_name': 'Y', 'email': 'attacker@example.com',
        })
        self.assertContains(response, 'Хандах эрхгүй')
        self.staff.refresh_from_db()
        self.assertNotEqual(self.staff.email, 'attacker@example.com')


class AddNewStudentTests(SchoolAccessTestBase):
    def test_staff_adding_student_assigns_target_school(self):
        """Staff-ийн өөрийн сургууль (энд байхгүй) биш, URL-ын сургууль оноогдоно."""
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('manage_school_by_level', args=[self.school_b.id, self.level.id]),
            {'add_user': '1', 'last_name': 'Бат', 'first_name': 'Дорж', 'email': 'dorj@example.com'},
        )
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(email='dorj@example.com')
        self.assertEqual(new_user.data.school, self.school_b)
        self.assertEqual(new_user.data.province, self.province_b)
        self.assertEqual(new_user.data.level, self.level)
        self.assertTrue(new_user.groups.filter(pk=self.school_b.group_id).exists())

    def test_province_manager_adding_student_assigns_target_school(self):
        self.client.force_login(self.province_manager_b)
        self.client.post(
            reverse('manage_school_by_level', args=[self.school_b.id, self.level.id]),
            {'add_user': '1', 'last_name': 'Бат', 'first_name': 'Сүх', 'email': 'sukh@example.com'},
        )
        new_user = User.objects.get(email='sukh@example.com')
        self.assertEqual(new_user.data.school, self.school_b)


class EnrollmentServiceTests(SchoolAccessTestBase):
    def setUp(self):
        from schools import enrollment
        from schools.models import EnrollmentLog
        self.enrollment = enrollment
        self.Log = EnrollmentLog

    def in_group(self, user, school):
        return user.groups.filter(pk=school.group_id).exists()

    def test_enroll_sets_school_province_level_group_and_logs(self):
        user = make_user('fresh')
        action = self.enrollment.enroll(user, self.school_a, by=self.moderator_a, level=self.level)
        user.data.refresh_from_db()
        self.assertEqual(action, self.Log.Action.ENROLL)
        self.assertEqual(user.data.school, self.school_a)
        self.assertEqual(user.data.province, self.province_a)
        self.assertEqual(user.data.level, self.level)
        self.assertTrue(self.in_group(user, self.school_a))
        log = self.Log.objects.get(user=user)
        self.assertEqual((log.to_school, log.performed_by), (self.school_a, self.moderator_a))

    def test_enroll_creates_missing_usermeta(self):
        user = User.objects.create_user(username='no_meta_enroll')
        self.enrollment.enroll(user, self.school_a)
        self.assertEqual(UserMeta.objects.get(user=user).school, self.school_a)

    def test_enroll_is_noop_for_existing_member(self):
        self.assertIsNone(self.enrollment.enroll(self.student_b, self.school_b))
        self.assertFalse(self.Log.objects.filter(user=self.student_b).exists())

    def test_transfer_leaves_old_group(self):
        action = self.enrollment.enroll(self.student_b, self.school_a, by=self.staff)
        self.assertEqual(action, self.Log.Action.TRANSFER)
        self.assertFalse(self.in_group(self.student_b, self.school_b))
        self.assertTrue(self.in_group(self.student_b, self.school_a))
        # дуудагчийн user.data cache шинэчлэгдсэн байх ёстой
        self.assertEqual(self.student_b.data.school, self.school_a)
        # UserMeta.save hook давхар UNENROLL log бичихгүй
        self.assertEqual(self.Log.objects.filter(user=self.student_b).count(), 1)

    def test_unenroll_clears_school_so_student_is_not_pending_again(self):
        self.assertTrue(self.enrollment.unenroll(self.student_b, self.school_b, by=self.moderator_b))
        self.student_b.data.refresh_from_db()
        self.assertIsNone(self.student_b.data.school)
        self.assertFalse(self.in_group(self.student_b, self.school_b))
        self.assertEqual(self.Log.objects.get(user=self.student_b).action, self.Log.Action.UNENROLL)

    def test_unenroll_non_member_is_noop(self):
        self.assertFalse(self.enrollment.unenroll(self.schoolless_student, self.school_a))

    def test_approve_requires_student_to_have_chosen_school(self):
        self.assertFalse(self.enrollment.approve(self.schoolless_student, self.school_a))
        self.assertFalse(self.in_group(self.schoolless_student, self.school_a))

    def test_usermeta_save_outside_service_leaves_old_group_and_logs(self):
        meta = self.student_b.data
        meta.school = self.school_a
        meta.save()
        self.assertFalse(self.in_group(self.student_b, self.school_b))
        log = self.Log.objects.get(user=self.student_b)
        self.assertEqual((log.action, log.from_school), (self.Log.Action.UNENROLL, self.school_b))


class PendingStudentsTests(SchoolAccessTestBase):
    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        from schools import enrollment
        self.enrollment = enrollment
        self.now = timezone.now()
        self.long_ago = self.now - timedelta(days=3 * 365)

    def make_pending(self, username, last_login):
        user = make_user(username, school=self.school_a, province=self.province_a)
        User.objects.filter(pk=user.pk).update(last_login=last_login)
        return user

    def test_only_recently_active_or_requested_students_are_pending(self):
        active = self.make_pending('active', self.now)
        stale = self.make_pending('stale', self.long_ago)
        never = self.make_pending('never', None)
        requested = self.make_pending('requested', None)
        self.enrollment.record_school_request(requested, None, self.school_a, by=requested)

        pending = set(self.enrollment.pending_students(self.school_a))
        self.assertEqual(pending, {active, requested})
        self.assertNotIn(stale, pending)
        self.assertNotIn(never, pending)

    def test_members_are_not_pending(self):
        active = self.make_pending('member', self.now)
        self.school_a.group.user_set.add(active)
        self.assertFalse(self.enrollment.pending_students(self.school_a).exists())

    def test_approve_all_skips_stale_predicted_students(self):
        active = self.make_pending('active2', self.now)
        stale = self.make_pending('stale2', self.long_ago)
        self.client.force_login(self.moderator_a)
        self.client.post(
            reverse('school_all_users', args=[self.school_a.id]), {'approve_all_users': '1'},
        )
        self.assertTrue(active.groups.filter(pk=self.school_a.group_id).exists())
        self.assertFalse(stale.groups.filter(pk=self.school_a.group_id).exists())

    def test_remove_user_view_unenrolls(self):
        self.client.force_login(self.moderator_b)
        self.client.post(
            reverse('school_all_users', args=[self.school_b.id]),
            {'remove_user': '1', 'user_id': self.student_b.id},
        )
        self.student_b.data.refresh_from_db()
        self.assertIsNone(self.student_b.data.school)
        self.assertNotIn(self.student_b, self.enrollment.pending_students(self.school_b))

    def test_profile_school_change_records_request(self):
        from schools.models import EnrollmentLog
        student = make_user('chooser', province=self.province_a)
        self.client.force_login(student)
        response = self.client.post(reverse('profile_edit'), {
            'last_name': 'Бат', 'first_name': 'Сараа', 'email': 'saraa@example.com',
            'reg_num': 'УБ12345678', 'province': self.province_a.id, 'school': self.school_a.id,
            'gender': 'Эм', 'mobile': '99112233', 'is_valid': 'on',
        })
        self.assertRedirects(response, reverse('user_profile'), fetch_redirect_response=False)
        log = EnrollmentLog.objects.get(user=student)
        self.assertEqual((log.action, log.to_school), (EnrollmentLog.Action.REQUEST, self.school_a))
        self.assertIn(student, self.enrollment.pending_students(self.school_a))

    def test_dashboard_lists_only_recent_pending(self):
        active = self.make_pending('dash_active', self.now)
        stale = self.make_pending('dash_stale', self.long_ago)
        self.client.force_login(self.moderator_a)
        response = self.client.get(reverse('school_dashboard', args=[self.school_a.id]))
        self.assertEqual(response.status_code, 200)
        pending = set(response.context['pending_students'])
        self.assertIn(active, pending)
        self.assertNotIn(stale, pending)


class ImportAnswerSheetTests(SchoolAccessTestBase):
    def setUp(self):
        from olympiad.models import Olympiad, Problem, Result
        self.olympiad = Olympiad.objects.create(name='ММО-I', level=self.level)
        self.p1 = Problem.objects.create(olympiad=self.olympiad, order=1)
        self.p2 = Problem.objects.create(olympiad=self.olympiad, order=2)
        self.student2 = make_user('student_b2', school=self.school_b, province=self.province_b)
        self.school_b.group.user_set.add(self.student2)
        self.existing = Result.objects.create(
            contestant=self.student_b, olympiad=self.olympiad, problem=self.p1, answer=99, score=3,
        )
        self.url = reverse('import_school_answer_sheet', args=[self.school_b.id, self.olympiad.id])

    def make_excel(self, rows):
        import io
        import pandas as pd
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            pd.DataFrame({'Түлхүүр': ['olympiad_id', 'school_id'],
                          'Утга': [self.olympiad.id, self.school_b.id]}).to_excel(
                writer, sheet_name='Мэдээлэл', index=False)
            pd.DataFrame(rows, columns=['ID', '№1', '№2']).to_excel(writer, sheet_name='Хариулт', index=False)
        buf.seek(0)
        buf.name = 'sheet.xlsx'
        return buf

    def test_import_creates_and_updates_results(self):
        from olympiad.models import Result
        self.client.force_login(self.moderator_b)
        rows = [
            [self.student_b.id, 12, 'abc'],       # p1 шинэчлэгдэнэ, p2 буруу формат -> None
            [self.student2.id, 5, 7.0],           # шинээр үүснэ
            [self.student_a_like().id, 1, 1],     # өөр сургууль -> алгасна
            [None, 1, 1],                         # хоосон ID -> алгасна
            [self.student2.id, 6, None],          # давхардсан мөр: сүүлийнх нь хүчинтэй
        ]
        response = self.client.post(self.url, {'file': self.make_excel(rows)}, follow=True)
        self.assertEqual(response.status_code, 200)

        self.existing.refresh_from_db()
        self.assertEqual(self.existing.answer, 12)
        self.assertEqual(self.existing.score, 3)  # бусад талбар хөндөгдөхгүй
        answers = dict(Result.objects.filter(olympiad=self.olympiad, contestant=self.student2)
                       .values_list('problem_id', 'answer'))
        self.assertEqual(answers, {self.p1.id: 6, self.p2.id: None})
        self.assertIsNone(Result.objects.get(contestant=self.student_b, problem=self.p2).answer)
        self.assertEqual(Result.objects.filter(olympiad=self.olympiad).count(), 4)

        msg = [str(m) for m in response.context['messages']][-1]
        self.assertIn('Үүссэн: 3', msg)
        self.assertIn('Шинэчлэгдсэн: 3', msg)
        self.assertIn('Буруу форматтай: 1', msg)
        self.assertIn('Алгассан: 2', msg)

    def test_query_count_does_not_grow_with_rows(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.client.force_login(self.moderator_b)
        students = [make_user(f'bulk_{i}', school=self.school_b) for i in range(40)]
        self.school_b.group.user_set.add(*students)

        def run(n):
            rows = [[s.id, 1, 2] for s in students[:n]]
            with CaptureQueriesContext(connection) as ctx:
                self.client.post(self.url, {'file': self.make_excel(rows)})
            return len(ctx.captured_queries)

        self.assertLess(run(40), 20)  # бүгд шинээр үүснэ
        self.assertEqual(run(5), run(40))  # бүгд шинэчлэгдэнэ

    def student_a_like(self):
        return make_user('other_school_student', school=self.school_a)


@override_settings(
    STORAGES=TEST_STORAGES,
    MAINTENANCE_MODE=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class ModeratorChangeNoticeTests(TestCase):
    """Бүртгэгч багш солигдоход удирдлага эсвэл аймгийн админд мэдэгдэл очих."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user('padmin', email='admin@aimag.mn')
        cls.province = Province.objects.create(name='Аймаг', contact_person=cls.admin)
        cls.old = make_user('old_teacher', email='old@school.mn')
        cls.new = make_user('new_teacher', email='new@school.mn')
        cls.manager = make_user('manager', email='director@school.mn')
        cls.school = School.objects.create(
            name='Сургууль', province=cls.province, user=cls.old, manager=cls.manager,
            group=Group.objects.create(name='School_notice'),
        )

    def setUp(self):
        # Celery-г тойрч task-ийг шууд ажиллуулна
        from unittest import mock
        from schools.tasks import send_moderator_changed_notice_task as task
        patcher = mock.patch.object(task, 'delay', side_effect=lambda *args: task(*args))
        patcher.start()
        self.addCleanup(patcher.stop)

    def change(self, by=None):
        from django.core import mail
        from schools.moderator import change_moderator
        with self.captureOnCommitCallbacks(execute=True):
            change_moderator(self.school, self.new, by or self.manager)
        return mail.outbox

    def test_manager_with_own_email_is_notified(self):
        outbox = self.change()
        self.school.refresh_from_db()
        self.assertEqual(self.school.user, self.new)
        self.assertEqual(len(outbox), 1)
        self.assertEqual(outbox[0].to, ['director@school.mn'])
        self.assertEqual(outbox[0].from_email, 'registration@mmo.mn')
        self.assertIn('old@school.mn', outbox[0].body)
        self.assertIn('new@school.mn', outbox[0].body)

    def test_manager_sharing_moderator_email_goes_to_province(self):
        self.manager.email = 'old@school.mn'
        self.manager.save()
        outbox = self.change()
        self.assertEqual(outbox[0].to, ['admin@aimag.mn'])
        self.assertIn('Анхаарна уу', outbox[0].body)

    def test_blacklisted_manager_email_goes_to_province(self):
        from emails.models import EmailBounce
        EmailBounce.objects.create(email='director@school.mn', bounce_type='hard')
        outbox = self.change()
        self.assertEqual(outbox[0].to, ['admin@aimag.mn'])

    def test_no_reachable_admin_falls_back_to_registration(self):
        self.manager.email = ''
        self.manager.save()
        self.admin.email = ''
        self.admin.save()
        outbox = self.change()
        self.assertEqual(outbox[0].to, ['registration@mmo.mn'])

    def test_same_moderator_sends_nothing(self):
        from django.core import mail
        from schools.moderator import change_moderator
        with self.captureOnCommitCallbacks(execute=True):
            change_moderator(self.school, self.old, self.manager)
        self.assertEqual(mail.outbox, [])

    def test_manager_view_uses_notice(self):
        from django.core import mail
        self.client.force_login(self.manager)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('manager_change_moderator', args=[self.school.id]),
                             {'assign_moderator': '1', 'user_id': self.new.id})
        self.school.refresh_from_db()
        self.assertEqual(self.school.user, self.new)
        self.assertEqual(len(mail.outbox), 1)


@override_settings(
    STORAGES=TEST_STORAGES,
    MAINTENANCE_MODE=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class ManageAllSchoolsBlockedEmailTests(SchoolAccessTestBase):
    def setUp(self):
        from emails.models import EmailBounce
        self.moderator_a.email = 'Bounced@School.mn'
        self.moderator_a.save()
        EmailBounce.objects.create(email='bounced@school.mn', bounce_type='hard')
        self.client.force_login(self.staff)

    def test_blocked_badge_shown(self):
        response = self.client.get(reverse('manage_all_schools'))
        self.assertContains(response, 'Имэйлд алдаа гарсан</span>', count=1)

    def test_manager_same_email_warning(self):
        manager = make_user('mgr_a', email='bounced@school.mn')
        self.school_a.manager = manager
        self.school_a.save()
        response = self.client.get(reverse('manage_all_schools'))
        self.assertContains(response, 'Бүртгэгч багшийн имэйлтэй ижил', count=1)

    def test_blocked_filter(self):
        response = self.client.get(reverse('manage_all_schools'), {'blocked': '1'})
        self.assertContains(response, 'Сургууль А')
        self.assertNotContains(response, 'Сургууль Б')


@override_settings(
    STORAGES=TEST_STORAGES,
    MAINTENANCE_MODE=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class AccessNoticeTests(SchoolAccessTestBase):
    def test_moderator_sees_own_role(self):
        self.client.force_login(self.moderator_a)
        response = self.client.get(reverse('school_dashboard', args=[self.school_a.id]))
        self.assertContains(response, 'Сургууль А-ийн бүртгэгч багш</strong> эрхээр')
        self.assertContains(response, 'зөвхөн албан хэрэгцээнд')

    def test_staff_sees_staff_role(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('school_dashboard', args=[self.school_a.id]))
        self.assertContains(response, '<strong>Staff</strong> эрхээр')

    def test_province_contact_sees_province_role(self):
        self.client.force_login(self.province_manager_b)
        response = self.client.get(reverse('school_dashboard', args=[self.school_b.id]))
        self.assertContains(response, 'Аймаг Б-ийн удирдах ажилтан')


@override_settings(
    STORAGES=TEST_STORAGES,
    MAINTENANCE_MODE=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class EditSchoolManagerAccountTests(SchoolAccessTestBase):
    """Сургуулийн удирдлагын албан аккаунтад зөвхөн албан тушаал, имэйл, утас засна."""

    def setUp(self):
        self.moderator_a.email = 'teacher@school.mn'
        self.moderator_a.save()
        self.manager = make_user('s0001', school=self.school_a, province=self.province_a,
                                 first_name='Менежер', last_name='Аймаг А Сургууль А', email='')
        self.school_a.manager = self.manager
        self.school_a.save()
        self.url = reverse('edit_school_admin', args=[self.manager.id])
        self.client.force_login(self.moderator_a)
        from unittest import mock
        from schools.tasks import send_account_email_changed_notice_task as task
        patcher = mock.patch.object(task, 'delay', side_effect=lambda *args: task(*args))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_shows_restricted_form(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'сургуулийн албан аккаунт')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="mobile"')
        for field in ('title', 'first_name', 'last_name', 'province'):
            self.assertNotContains(response, f'name="{field}"')

    def test_updates_only_email_mobile_and_restores_name(self):
        self.manager.first_name, self.manager.last_name = 'Энхмэнд', 'Баттулга'
        self.manager.save()
        response = self.client.post(self.url, {
            'email': 'Director@School.mn', 'mobile': '99112233',
            'first_name': 'Хакер', 'last_name': 'Хакер', 'province': self.province_b.id,
        })
        self.assertRedirects(response, reverse('school_dashboard', args=[self.school_a.id]))
        self.manager.refresh_from_db()
        self.assertEqual((self.manager.first_name, self.manager.last_name), ('Менежер', 'Аймаг А Сургууль А'))
        self.assertEqual(self.manager.email, 'director@school.mn')
        self.assertEqual(self.manager.data.mobile, 99112233)
        self.assertEqual(self.manager.data.province, self.province_a)

    def test_rejects_moderator_email(self):
        response = self.client.post(self.url, {'email': 'TEACHER@school.mn', 'mobile': '99112233'})
        self.assertContains(response, 'Бүртгэгч багшийн имэйлтэй ижил байж болохгүй')
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.email, '')

    def test_rejects_invalid_mobile(self):
        response = self.client.post(self.url, {'email': 'd@school.mn', 'mobile': '185734'})
        self.assertContains(response, '8 оронтой утасны дугаар')

    def test_personal_moderator_account_keeps_full_form(self):
        response = self.client.get(reverse('edit_school_admin', args=[self.moderator_a.id]))
        self.assertContains(response, 'name="last_name"')


@override_settings(
    STORAGES=TEST_STORAGES,
    MAINTENANCE_MODE=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class EditProvinceAdminAccountTests(SchoolAccessTestBase):
    """Аймгийн удирдах ажилтны албан аккаунтад зөвхөн албан тушаал, имэйл, утас засна."""

    def setUp(self):
        self.contact = self.province_manager_b
        self.contact.first_name = 'Удирдах ажилтан'
        self.contact.last_name = 'Аймаг Б'
        self.contact.save()
        self.url = reverse('edit_province_admin', args=[self.contact.id])
        self.client.force_login(self.contact)

    def test_shows_restricted_form(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Аймаг Б-ийн албан аккаунт')
        self.assertNotContains(response, 'name="title"')
        self.assertNotContains(response, 'name="last_name"')

    def test_updates_only_email_mobile_and_restores_name(self):
        self.contact.first_name, self.contact.last_name = 'Ариунжаргал', 'Зандраа'
        self.contact.save()
        response = self.client.post(self.url, {
            'email': 'aimag@edu.mn', 'mobile': '88112233', 'last_name': 'Хакер',
        })
        self.assertRedirects(response, reverse('province_dashboard', args=[self.province_b.id]),
                             fetch_redirect_response=False)
        self.contact.refresh_from_db()
        self.assertEqual((self.contact.first_name, self.contact.last_name, self.contact.email),
                         ('Удирдах ажилтан', 'Аймаг Б', 'aimag@edu.mn'))
        self.assertEqual(self.contact.data.mobile, 88112233)

    def test_registrar_keeps_full_form(self):
        registrar = make_user('registrar_b', province=self.province_b)
        self.province_b.registrar = registrar
        self.province_b.save()
        response = self.client.get(reverse('edit_province_admin', args=[registrar.id]))
        self.assertContains(response, 'name="last_name"')


@override_settings(
    STORAGES=TEST_STORAGES,
    MAINTENANCE_MODE=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class AccountEmailChangedNoticeTests(SchoolAccessTestBase):
    """Албан аккаунтын имэйл солигдоход хуучин хаяг (эсвэл аймгийн админ) руу мэдэгдэл очих."""

    def setUp(self):
        from unittest import mock
        from schools.tasks import send_account_email_changed_notice_task as task
        patcher = mock.patch.object(task, 'delay', side_effect=lambda *args: task(*args))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.province_manager_a = make_user('pm_a', email='aimag@edu.mn')
        self.province_a.contact_person = self.province_manager_a
        self.province_a.save()
        self.manager = make_user('s0001', school=self.school_a, province=self.province_a,
                                 first_name='Менежер', last_name='Аймаг А Сургууль А', email='old@director.mn')
        self.school_a.manager = self.manager
        self.school_a.save()
        self.url = reverse('edit_school_admin', args=[self.manager.id])
        self.client.force_login(self.moderator_a)

    def post(self, email):
        from django.core import mail
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url, {'email': email, 'mobile': '99112233'})
        return mail.outbox

    def test_old_address_is_notified(self):
        outbox = self.post('new@director.mn')
        self.assertEqual(len(outbox), 1)
        self.assertEqual(outbox[0].to, ['old@director.mn'])
        self.assertIn('new@director.mn', outbox[0].body)
        self.assertIn('mod_a', outbox[0].body)

    def test_unchanged_email_sends_nothing(self):
        self.assertEqual(self.post('OLD@director.mn'), [])

    def test_missing_old_email_goes_to_province_admin(self):
        self.manager.email = ''
        self.manager.save()
        outbox = self.post('new@director.mn')
        self.assertEqual(outbox[0].to, ['aimag@edu.mn'])
        self.assertIn('Анхаарна уу', outbox[0].body)

    def test_blocked_old_email_goes_to_province_admin(self):
        from emails.models import EmailBounce
        EmailBounce.objects.create(email='old@director.mn', bounce_type='hard')
        outbox = self.post('new@director.mn')
        self.assertEqual(outbox[0].to, ['aimag@edu.mn'])



class RestoreInstitutionalNamesTests(SchoolAccessTestBase):
    def test_restores_personal_and_stale_names_only_for_institutional_accounts(self):
        from io import StringIO
        from django.core.management import call_command
        manager = make_user('s0001', first_name='Энхмэнд', last_name='Баттулга')
        personal = make_user('teacher_mgr', first_name='Бат', last_name='Дорж')
        self.school_a.manager = manager
        self.school_a.save()
        self.school_b.manager = personal
        self.school_b.save()
        self.province_manager_b.username = 'padmin02'
        self.province_manager_b.first_name = 'Ариунжаргал'
        self.province_manager_b.save()

        call_command('restore_institutional_names', stdout=StringIO())  # dry-run
        manager.refresh_from_db()
        self.assertEqual(manager.first_name, 'Энхмэнд')

        call_command('restore_institutional_names', '--apply', stdout=StringIO())
        manager.refresh_from_db(); personal.refresh_from_db(); self.province_manager_b.refresh_from_db()
        self.assertEqual((manager.first_name, manager.last_name), ('Менежер', 'Аймаг А Сургууль А'))
        self.assertEqual((personal.first_name, personal.last_name), ('Бат', 'Дорж'))
        self.assertEqual((self.province_manager_b.first_name, self.province_manager_b.last_name),
                         ('Удирдах ажилтан', 'Аймаг Б'))
