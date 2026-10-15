from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from accounts import activation
from accounts.forms import CustomPasswordResetForm
from schools.email_service import SchoolEmailService

from .models import EmailBounce
from .suppression import email_typo_suggestion, is_undeliverable, validate_no_email_typo


class IsUndeliverableTests(TestCase):
    def test_hard_bounce_and_complaint_block(self):
        EmailBounce.objects.create(email='gone@example.com', bounce_type='hard')
        EmailBounce.objects.create(email='angry@example.com', bounce_type='complaint')
        self.assertTrue(is_undeliverable('gone@example.com'))
        self.assertTrue(is_undeliverable('angry@example.com'))

    def test_soft_bounce_does_not_block(self):
        EmailBounce.objects.create(email='full@example.com', bounce_type='soft')
        self.assertFalse(is_undeliverable('full@example.com'))

    def test_case_and_whitespace_insensitive_for_lowercase_records(self):
        EmailBounce.objects.create(email='gone@example.com', bounce_type='hard')
        self.assertTrue(is_undeliverable('  Gone@Example.com '))

    def test_empty_is_not_undeliverable(self):
        self.assertFalse(is_undeliverable(''))
        self.assertFalse(is_undeliverable(None))


class TypoTests(TestCase):
    def test_known_typos_get_a_suggestion(self):
        self.assertEqual(email_typo_suggestion('a@gmmail.com'), 'a@gmail.com')
        self.assertEqual(email_typo_suggestion('a@Gamil.com'), 'a@gmail.com')
        self.assertEqual(email_typo_suggestion('a@ayhoo.com'), 'a@yahoo.com')

    def test_real_domains_are_left_alone(self):
        for addr in ('a@gmail.com', 'a@moes.edu.mn', 'a@gmail.ru', 'a@hmail.com', 'nope'):
            self.assertIsNone(email_typo_suggestion(addr), addr)

    def test_validator_raises_with_suggestion(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_no_email_typo('b@gmmail.com')
        self.assertIn('b@gmail.com', ctx.exception.messages[0])
        validate_no_email_typo('b@gmail.com')
        validate_no_email_typo(None)


class SendersSkipUndeliverableTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('u1', email='gone@example.com', password='x')
        EmailBounce.objects.create(email='gone@example.com', bounce_type='hard')

    def test_activation_email_is_not_sent(self):
        request = RequestFactory().get('/')
        with mock.patch('accounts.activation.text_email') as te:
            self.assertFalse(activation.send_activation_email(request, self.user))
        te.assert_not_called()
        self.assertTrue(activation.recently_sent(self.user))

    def test_activation_email_still_sent_for_good_address(self):
        good = User.objects.create_user('u2', email='ok@example.com', password='x')
        request = RequestFactory().get('/')
        with mock.patch('accounts.activation.text_email') as te:
            self.assertTrue(activation.send_activation_email(request, good))
        te.return_value.send.assert_called_once()

    def test_school_service_skips_all_three_senders(self):
        with mock.patch('schools.email_service.EmailMultiAlternatives') as em:
            for ok, err in (
                SchoolEmailService.send_password_reset_link(self.user),
                SchoolEmailService.send_new_user_welcome_with_reset_link(self.user, 'School'),
                SchoolEmailService.send_password_reset_notification(self.user, 'pw'),
            ):
                self.assertFalse(ok)
                self.assertIn('bounce', err)
        em.assert_not_called()

    def test_password_reset_skips_undeliverable(self):
        form = CustomPasswordResetForm({'email': 'u1'})
        self.assertTrue(form.is_valid())
        with mock.patch.object(CustomPasswordResetForm, 'send_mail') as sm:
            form.save(request=RequestFactory().get('/'))
        sm.assert_not_called()


class PasswordResetCooldownTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('u3', email='ok@example.com', password='x')

    def _submit(self):
        form = CustomPasswordResetForm({'email': 'u3'})
        self.assertTrue(form.is_valid())
        with mock.patch.object(CustomPasswordResetForm, 'send_mail') as sm:
            form.save(request=RequestFactory().get('/'))
        return sm.call_count

    def test_second_request_within_cooldown_is_not_sent(self):
        self.assertEqual(self._submit(), 1)
        self.assertEqual(self._submit(), 0)
