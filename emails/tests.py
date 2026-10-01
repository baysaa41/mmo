import base64
import datetime
import json
from unittest import mock

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import EmailBounce, EmailEvent
from .sns import _SIGNED_FIELDS

TOPIC = 'arn:aws:sns:us-west-2:545682170977:mailer'
CERT_URL = 'https://sns.us-west-2.amazonaws.com/SimpleNotificationService-test.pem'


def _make_key_and_cert():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'sns.amazonaws.com')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(1).not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256()))
    return key, cert.public_bytes(serialization.Encoding.PEM)


KEY, CERT_PEM = _make_key_and_cert()


def signed(data, key=KEY, version='1'):
    data = {'TopicArn': TOPIC, 'SigningCertURL': CERT_URL, 'SignatureVersion': version,
            'MessageId': 'mid', 'Timestamp': '2026-10-01T01:00:00.000Z', **data}
    canonical = ''.join(f'{f}\n{data[f]}\n' for f in _SIGNED_FIELDS[data['Type']] if f in data).encode()
    algorithm = hashes.SHA256() if version == '2' else hashes.SHA1()
    data['Signature'] = base64.b64encode(key.sign(canonical, padding.PKCS1v15(), algorithm)).decode()
    return data


def ses_event(event_type, detail):
    return {
        'eventType': event_type,
        'mail': {'messageId': '010101a0-abc-000000', 'timestamp': '2026-10-01T00:00:00.000Z',
                 'destination': ['teacher@school.mn'], 'commonHeaders': {'subject': 'ММО-63: сургуулийн бүртгэл'}},
        event_type.lower(): detail,
    }


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
                   MAINTENANCE_MODE=False, AWS_SNS_VERIFY='enforce')
class SnsWebhookTests(TestCase):
    def setUp(self):
        response = mock.Mock(content=CERT_PEM)
        patcher = mock.patch('emails.sns.requests.get', return_value=response)
        self.cert_get = patcher.start()
        self.addCleanup(patcher.stop)
        self.url = reverse('sns_notification')

    def post(self, data):
        return self.client.post(self.url, json.dumps(data), content_type='application/json')

    def notification(self, message, **kwargs):
        return signed({'Type': 'Notification', 'Message': json.dumps(message), **kwargs})

    def test_open_event_is_recorded(self):
        response = self.post(self.notification(ses_event('Open', {
            'timestamp': '2026-10-01T03:15:00.000Z', 'userAgent': 'Mozilla/5.0'})))
        self.assertEqual(response.status_code, 200)
        event = EmailEvent.objects.get()
        self.assertEqual((event.event_type, event.email, event.message_id),
                         ('open', 'teacher@school.mn', '010101a0-abc-000000'))
        self.assertEqual(event.subject, 'ММО-63: сургуулийн бүртгэл')

    def test_click_event_records_link_with_signature_v2(self):
        self.post(signed({'Type': 'Notification', 'Message': json.dumps(ses_event('Click', {
            'timestamp': '2026-10-01T03:16:00.000Z', 'link': 'https://www.mmo.mn/accounts/login/'}))}, version='2'))
        self.assertEqual(EmailEvent.objects.get().link, 'https://www.mmo.mn/accounts/login/')

    def test_delivery_event_uses_recipients(self):
        self.post(self.notification(ses_event('Delivery', {
            'timestamp': '2026-10-01T01:50:00.000Z', 'recipients': ['teacher@school.mn']})))
        self.assertEqual(EmailEvent.objects.get().event_type, 'delivery')

    def test_event_bounce_is_not_double_counted(self):
        self.post(self.notification(ses_event('Bounce', {'bounceType': 'Permanent'})))
        self.assertFalse(EmailEvent.objects.exists())
        self.assertFalse(EmailBounce.objects.exists())

    def test_identity_bounce_notification_still_recorded(self):
        self.post(self.notification({
            'notificationType': 'Bounce',
            'bounce': {'bounceType': 'Permanent', 'bouncedRecipients': [{'emailAddress': 'x@school.mn'}]},
            'mail': {'messageId': 'm1'},
        }))
        self.assertEqual(EmailBounce.objects.get().bounce_type, 'hard')

    def test_tampered_message_rejected(self):
        data = self.notification(ses_event('Open', {'timestamp': '2026-10-01T03:15:00.000Z'}))
        data['Message'] = data['Message'].replace('teacher@school.mn', 'attacker@evil.mn')
        self.assertEqual(self.post(data).status_code, 403)
        self.assertFalse(EmailEvent.objects.exists())

    def test_other_key_rejected(self):
        other_key, _ = _make_key_and_cert()
        data = signed({'Type': 'Notification', 'Message': '{}'}, key=other_key)
        self.assertEqual(self.post(data).status_code, 403)

    def test_unknown_topic_rejected(self):
        self.assertEqual(self.post(self.notification({}, TopicArn='arn:aws:sns:us-west-2:1:evil')).status_code, 403)

    def test_cert_url_must_be_amazon(self):
        data = self.notification({}, SigningCertURL='https://evil.example.com/cert.pem')
        self.assertEqual(self.post(data).status_code, 403)
        self.cert_get.assert_not_called()

    def test_subscribe_url_must_be_amazon(self):
        data = signed({'Type': 'SubscriptionConfirmation', 'Token': 't', 'Message': 'm',
                       'SubscribeURL': 'https://169.254.169.254/latest/meta-data/'})
        self.assertEqual(self.post(data).status_code, 400)
        # requests.get нь зөвхөн сертификатад (кэшлэгдсэн бол огт) дуудагдана — SubscribeURL руу хандахгүй
        for call in self.cert_get.call_args_list:
            self.assertEqual(call.args[0], CERT_URL)


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
                   MAINTENANCE_MODE=False, AWS_SNS_VERIFY='log')
class SnsLogOnlyModeTests(TestCase):
    def test_unverified_message_still_processed_and_logged(self):
        data = {'Type': 'Notification', 'TopicArn': TOPIC, 'Message': json.dumps(ses_event(
            'Open', {'timestamp': '2026-10-01T03:15:00.000Z'}))}
        with self.assertLogs('emails.views', level='WARNING') as logs:
            response = self.client.post(reverse('sns_notification'), json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(EmailEvent.objects.exists())
        self.assertIn('verified=False', logs.output[0])
