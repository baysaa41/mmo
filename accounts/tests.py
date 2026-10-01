from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Grade, Province, UserMeta
from accounts.services import generate_styled_user_dataframe_html
from schools.models import School


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    MAINTENANCE_MODE=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class GroupUsersTableTests(TestCase):
    """pandas 3 + django-pandas read_frame-ийн TypeError-ийн регресс."""

    @classmethod
    def setUpTestData(cls):
        cls.group = Group.objects.create(name='Сургууль А')
        province = Province.objects.create(name='Аймаг А')
        school = School.objects.create(name='Сургууль А', province=province, group=cls.group)
        grade = Grade.objects.create(name='7')

        cls.full = User.objects.create_user('full', first_name='Дорж', last_name='Бат')
        UserMeta.objects.create(user=cls.full, province=province, school=school, grade=grade,
                                reg_num='УБ12345678', mobile=99112233)
        # Профайлгүй, утасгүй хэрэглэгч: хоосон утгууд алдаа гаргахгүй байх ёстой
        cls.bare = User.objects.create_user('bare', first_name='Сараа', last_name='Болд')
        cls.group.user_set.add(cls.full, cls.bare)

    def test_non_staff_table_renders(self):
        response = self.client.get(reverse('group_users', args=[self.group.id]))
        self.assertEqual(response.status_code, 200)
        html = response.context['pivot']
        for text in ('Дорж', 'Сараа', 'Сургууль А', 'Аймаг А'):
            self.assertIn(text, html)

    def test_staff_columns_include_mobile_as_integer(self):
        html = generate_styled_user_dataframe_html(self.group.user_set.order_by('id'), is_staff=True)
        self.assertIn('99112233', html)
        self.assertNotIn('99112233.0', html)
        self.assertIn('УБ12345678', html)

    def test_empty_queryset_renders(self):
        html = generate_styled_user_dataframe_html(User.objects.none())
        self.assertIn('Хэрэглэгчийн нэр', html)


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'last-activity-tests'}})
class LastActivityMiddlewareTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(username='activity-user', password='pw')
        UserMeta.objects.create(user=self.user, reg_num='')

    def test_authenticated_request_sets_last_activity(self):
        self.client.force_login(self.user)
        self.client.get('/')
        self.assertIsNotNone(UserMeta.objects.get(user=self.user).last_activity)

    def test_updates_are_throttled(self):
        self.client.force_login(self.user)
        self.client.get('/')
        UserMeta.objects.filter(user=self.user).update(last_activity=None)
        self.client.get('/')
        self.assertIsNone(UserMeta.objects.get(user=self.user).last_activity)

    def test_anonymous_request_is_ignored(self):
        self.client.get('/')
        self.assertIsNone(UserMeta.objects.get(user=self.user).last_activity)

    def test_user_without_meta_does_not_error(self):
        other = User.objects.create_user(username='no-meta', password='pw')
        self.client.force_login(other)
        self.assertLess(self.client.get('/').status_code, 500)


class AdvanceGradesCommandTests(TestCase):
    """advance_grades нь хичээлийн жилд нэг л удаа ажиллаж, лог үлдээнэ."""

    def setUp(self):
        import datetime
        import tempfile
        from unittest import mock
        from olympiad.models import SchoolYear
        today = datetime.date.today()
        SchoolYear.objects.create(name='test', start=today - datetime.timedelta(days=30),
                                  end=today + datetime.timedelta(days=300))
        from accounts.models import Level
        for grade_id in range(1, 18):
            Grade.objects.get_or_create(id=grade_id, defaults={'name': str(grade_id)})
        for level_id in range(1, 9):
            Level.objects.get_or_create(id=level_id, defaults={'name': str(level_id)})
        self.student = User.objects.create_user('student5')
        UserMeta.objects.create(user=self.student, grade_id=5)
        self.log = tempfile.NamedTemporaryFile(suffix='.log', delete=False).name
        patcher = mock.patch('accounts.management.commands.advance_grades.log_path', return_value=self.log)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_command(self, *args):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('advance_grades', *args, stdout=out)
        return out.getvalue()

    def test_advances_once_and_logs(self):
        from django.core.management.base import CommandError
        self.run_command('--yes')
        self.assertEqual(UserMeta.objects.get(user=self.student).grade_id, 6)
        with open(self.log, encoding='utf-8') as f:
            self.assertIn('"action": "advanced"', f.read())
        with self.assertRaises(CommandError):
            self.run_command('--yes')
        self.assertEqual(UserMeta.objects.get(user=self.student).grade_id, 6)

    def test_check_and_mark_done_do_not_change_grades(self):
        from django.core.management.base import CommandError
        self.assertIn('ахиулаагүй', self.run_command('--check'))
        self.run_command('--mark-done', 'гараар хийсэн')
        with self.assertRaises(CommandError):
            self.run_command('--yes')
        self.assertEqual(UserMeta.objects.get(user=self.student).grade_id, 5)
