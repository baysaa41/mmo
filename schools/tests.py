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
