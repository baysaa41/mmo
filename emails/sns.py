"""
AWS SNS мессежийн гарын үсгийг шалгах ба SES-ийн үйл явдлыг (Open, Click, Delivery) хадгалах.

SNS webhook нь нийтэд нээлттэй тул гарын үсэггүй, эсвэл зөвшөөрөгдөөгүй topic-оос ирсэн
мессежийг хүлээж авахгүй — эс бөгөөс хэн ч хуурамч bounce/нээлт бүртгэж, дурын
SubscribeURL руу манай серверээр хүсэлт илгээлгэх боломжтой.
https://docs.aws.amazon.com/sns/latest/dg/sns-verify-signature-of-message.html
"""
import base64
import logging
import re
from urllib.parse import urlparse

import requests
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings
from django.core.cache import cache
from django.utils.dateparse import parse_datetime

from .models import EmailEvent

logger = logging.getLogger(__name__)

DEFAULT_TOPIC_ARNS = ['arn:aws:sns:us-west-2:545682170977:mailer']
_SNS_HOST_RE = re.compile(r'^sns\.[a-z0-9-]+\.amazonaws\.com$')

_SIGNED_FIELDS = {
    'Notification': ['Message', 'MessageId', 'Subject', 'Timestamp', 'TopicArn', 'Type'],
    'SubscriptionConfirmation': ['Message', 'MessageId', 'SubscribeURL', 'Timestamp', 'Token', 'TopicArn', 'Type'],
    'UnsubscribeConfirmation': ['Message', 'MessageId', 'SubscribeURL', 'Timestamp', 'Token', 'TopicArn', 'Type'],
}


def allowed_topic_arns():
    return getattr(settings, 'AWS_SNS_TOPIC_ARNS', DEFAULT_TOPIC_ARNS)


def is_sns_url(url):
    parsed = urlparse(url or '')
    return parsed.scheme == 'https' and bool(_SNS_HOST_RE.match(parsed.hostname or ''))


def _certificate(url):
    key = f'sns_cert:{url}'
    pem = cache.get(key)
    if pem is None:
        pem = requests.get(url, timeout=10).content
        cache.set(key, pem, 60 * 60 * 24)
    return x509.load_pem_x509_certificate(pem)


def verify_sns_message(data):
    """Гарын үсэг зөв, topic зөвшөөрөгдсөн бол True."""
    message_type = data.get('Type')
    if message_type not in _SIGNED_FIELDS or data.get('TopicArn') not in allowed_topic_arns():
        return False
    cert_url = data.get('SigningCertURL', '')
    if not is_sns_url(cert_url) or not urlparse(cert_url).path.endswith('.pem'):
        return False

    canonical = ''.join(
        f'{field}\n{data[field]}\n' for field in _SIGNED_FIELDS[message_type] if field in data
    ).encode('utf-8')
    algorithm = hashes.SHA256() if data.get('SignatureVersion') == '2' else hashes.SHA1()
    try:
        _certificate(cert_url).public_key().verify(
            base64.b64decode(data.get('Signature', '')), canonical, padding.PKCS1v15(), algorithm)
    except (InvalidSignature, ValueError, requests.RequestException) as exc:
        logger.warning('SNS signature verification failed: %s', exc)
        return False
    return True


_EVENT_DETAILS = {'Open': 'open', 'Click': 'click', 'Delivery': 'delivery'}


def record_ses_event(message):
    """Configuration set-ийн event (eventType бүхий) мессежийг хадгална. Хадгалсан тоог буцаана."""
    event_type = message.get('eventType')
    detail_key = _EVENT_DETAILS.get(event_type)
    if not detail_key:
        return 0  # Send, Bounce, Complaint гэх мэт — bounce-ыг identity мэдэгдлээр аль хэдийн бүртгэдэг
    mail = message.get('mail', {})
    detail = message.get(detail_key, {})
    occurred_at = parse_datetime(detail.get('timestamp') or mail.get('timestamp') or '')
    if occurred_at is None:
        return 0
    subject = (mail.get('commonHeaders') or {}).get('subject', '')
    recipients = detail.get('recipients') or mail.get('destination') or []
    EmailEvent.objects.bulk_create([
        EmailEvent(
            message_id=mail.get('messageId', ''),
            email=recipient[:254],
            event_type=EmailEvent.OPEN if event_type == 'Open' else
            EmailEvent.CLICK if event_type == 'Click' else EmailEvent.DELIVERY,
            occurred_at=occurred_at,
            link=(detail.get('link') or '')[:2000],
            user_agent=(detail.get('userAgent') or '')[:500],
            subject=subject[:255],
        )
        for recipient in recipients
    ])
    return len(recipients)
