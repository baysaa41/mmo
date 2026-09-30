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
