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


class RegistrationDoubleSubmitTests(TestCase):
    def test_duplicate_username_race_shows_form_error(self):
        from unittest import mock
        from django.db import IntegrityError
        from accounts.views.auth import RegistrationViewWithCaptcha

        data = {'username': 'racetest', 'email': 'racetest@example.com',
                'password1': 'Xk9!qweRTY12', 'password2': 'Xk9!qweRTY12', 'captcha': 'x'}
        err = IntegrityError('duplicate key value violates unique constraint "idx_24017_username"')
        with mock.patch('accounts.forms.ResilientReCaptchaField.validate'), \
                mock.patch.object(RegistrationViewWithCaptcha, 'create_inactive_user', side_effect=err):
            response = self.client.post(reverse('django_registration_register'), data,
                                        HTTP_X_REAL_IP='127.0.0.1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'аль хэдийн үүссэн')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class ResendActivationTests(TestCase):
    IP = {'HTTP_X_REAL_IP': '127.0.0.1'}

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.url = reverse('resend_activation')

    def _pending(self, username, email='shared@example.com'):
        u = User.objects.create(username=username, email=email, is_active=False)
        u.set_password('Xk9!qweRTY12')
        u.save()
        return u

    def test_single_pending_account_gets_one_email_with_working_link(self):
        from django.core import mail
        self._pending('solo', 'solo@example.com')
        response = self.client.post(self.url, {'identifier': 'solo@example.com'}, **self.IP)
        self.assertContains(response, 'илгээлээ')
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['solo@example.com'])
        self.assertTrue(msg.alternatives)
        link = next(w for w in msg.body.split() if '/accounts/activate/' in w)
        self.client.get(link.split('testserver', 1)[1], **self.IP)
        self.assertTrue(User.objects.get(username='solo').is_active)

    def test_shared_email_asks_to_choose_and_sends_only_one(self):
        from django.core import mail
        for name in ('kid1', 'kid2', 'kid3'):
            self._pending(name)
        response = self.client.post(self.url, {'identifier': 'shared@example.com'}, **self.IP)
        self.assertContains(response, 'kid2')
        self.assertEqual(len(mail.outbox), 0)
        self.client.post(self.url, {'identifier': 'shared@example.com', 'selected_username': 'kid2'}, **self.IP)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('kid2', mail.outbox[0].body)

    def test_repeat_request_within_cooldown_does_not_resend(self):
        from django.core import mail
        self._pending('again', 'again@example.com')
        self.client.post(self.url, {'identifier': 'again'}, **self.IP)
        self.client.post(self.url, {'identifier': 'again'}, **self.IP)
        self.assertEqual(len(mail.outbox), 1)

    def test_active_or_deactivated_accounts_are_not_sent(self):
        from django.core import mail
        from django.utils import timezone
        User.objects.create(username='active1', email='a@example.com', is_active=True)
        User.objects.create(username='banned', email='b@example.com', is_active=False, last_login=timezone.now())
        self.assertContains(self.client.post(self.url, {'identifier': 'active1'}, **self.IP), 'аль хэдийн идэвхтэй')
        self.assertContains(self.client.post(self.url, {'identifier': 'banned'}, **self.IP), 'олдсонгүй')
        self.assertEqual(len(mail.outbox), 0)

    def test_login_with_pending_account_offers_resend(self):
        self._pending('waiting', 'w@example.com')
        response = self.client.post(reverse('user_login'),
                                    {'username': 'waiting', 'password': 'Xk9!qweRTY12'}, **self.IP)
        self.assertContains(response, 'идэвхжээгүй')
        self.assertContains(response, reverse('resend_activation') + '?u=waiting')


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    MAINTENANCE_MODE=False,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class PasswordHasherUpgradeTests(TestCase):
    """Шинэ hash scrypt; хуучин PBKDF2 hash-тай хэрэглэгч нэвтрэхэд scrypt-д шилжинэ."""

    PASSWORD = 'Xk29!mmoNewPass'

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.hashers import get_hasher
        cls.user = User.objects.create(username='old_hash_user', is_active=True)
        UserMeta.objects.create(user=cls.user)
        # production-д байгаа хуучин hash: PBKDF2 (тест хурдан байхын тулд цөөн давталттай)
        cls.user.password = get_hasher('pbkdf2_sha256').encode(cls.PASSWORD, 'oldsalt', iterations=1000)
        cls.user.save()

    def login(self, password):
        return self.client.post(reverse('user_login'), {'username': 'old_hash_user', 'password': password})

    def test_settings_prefer_scrypt_and_keep_pbkdf2_for_existing_hashes(self):
        from django.conf import settings
        self.assertEqual(settings.PASSWORD_HASHERS[0], 'django.contrib.auth.hashers.ScryptPasswordHasher')
        self.assertIn('django.contrib.auth.hashers.PBKDF2PasswordHasher', settings.PASSWORD_HASHERS)

    def test_old_pbkdf2_hash_is_accepted_and_upgraded_to_scrypt_on_login(self):
        self.assertTrue(self.user.password.startswith('pbkdf2_sha256$'))
        response = self.login(self.PASSWORD)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)
        self.user.refresh_from_db()
        self.assertTrue(self.user.password.startswith('scrypt$'))
        self.assertTrue(self.user.check_password(self.PASSWORD))

    def test_wrong_password_is_rejected_and_hash_unchanged(self):
        before = self.user.password
        response = self.login('wrong-password')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, before)


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    MAINTENANCE_MODE=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class LoginFailureLoggingTests(TestCase):
    """Амжилтгүй нэвтрэлтийн шалтгаан нь нууц мэдээлэлгүйгээр log-д бичигдэнэ."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('real_user', password='Right-Pass-123')
        UserMeta.objects.create(user=cls.user)

    def failed_login(self, username, password):
        with self.assertLogs('accounts.login_failures', level='INFO') as captured:
            response = self.client.post(reverse('user_login'), {'username': username, 'password': password})
        self.assertEqual(response.status_code, 200)
        return captured.output

    def test_bad_password_is_logged_without_credentials(self):
        out = self.failed_login('real_user', 'Wrong-Pass-999')
        self.assertEqual(len(out), 1)
        self.assertIn('reason=bad_password', out[0])
        self.assertIn('alg=md5', out[0])
        self.assertNotIn('real_user', out[0])
        self.assertNotIn('Wrong-Pass-999', out[0])

    def test_unknown_username_is_logged(self):
        self.assertIn('reason=user_not_found ', self.failed_login('nobody', 'x')[0] + ' ')

    def test_username_case_mismatch_is_distinguished(self):
        """Form iexact-аар давдаг ч authenticate exact тул hash хоосон тооцогддог тохиолдол."""
        out = self.failed_login('REAL_USER', 'Right-Pass-123')
        self.assertIn('reason=username_case_mismatch', out[0])
        self.assertNotIn('REAL_USER', out[0])

    def test_email_instead_of_username_is_distinguished(self):
        out = self.failed_login('someone@example.com', 'x')
        self.assertIn('reason=user_not_found_email_like', out[0])
        self.assertNotIn('someone@example.com', out[0])

    def test_successful_login_writes_no_failure_log(self):
        with self.assertNoLogs('accounts.login_failures', level='INFO'):
            response = self.client.post(reverse('user_login'), {'username': 'real_user', 'password': 'Right-Pass-123'})
        self.assertEqual(response.status_code, 302)
