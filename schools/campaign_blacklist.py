"""
Бөөн имэйл кампанит ажлын (ММО-63 I давааны мэдээлэл гэх мэт) хар жагсаалт.

blocked_emails() (hard bounce, complaint, unsubscribe) дээр нэмж SES-ийн нэр хүндийг хамгаалахын
тулд дараах хаягуудыг хасна:
  - SES дансны suppression list (манай DB-д бүртгэгдээгүй bounce/complaint байж болно),
  - 2-оос дээш удаа soft bounce авсан хаяг,
  - өмнөх кампанит ажилд 'bounced' төлөвтэй болсон хаяг,
  - илгээх үед алдаа (failed) гарсан хаяг,
  - бөөнөөр үүсгэсэн системийн хаягууд (SYSTEM_EMAILS).
"""
import logging
from collections import Counter

from django.conf import settings

from schools.moderator import blocked_emails, norm_email

logger = logging.getLogger(__name__)

# Олон мянган аккаунтыг бөөнөөр үүсгэсэн хаягууд — хувь хүн биш тул кампанит ажилд оруулахгүй
SYSTEM_EMAILS = {
    'mmo60official@gmail.com',  # ММО-60-д бөөнөөр үүсгэсэн
    'auto-user@mmo.mn',         # систем
    'dm2020baysa@gmail.com',    # бөөн бүртгэлийн хаяг
}
SOFT_BOUNCE_LIMIT = 2


def ses_suppressed_emails():
    """SES дансны suppression list. Холбогдож чадахгүй бол хоосон олонлог буцаана."""
    import boto3
    try:
        client = boto3.client('sesv2', **settings.ANYMAIL['AMAZON_SES_CLIENT_PARAMS'])
        emails, token = set(), None
        while True:
            kwargs = {'PageSize': 1000, **({'NextToken': token} if token else {})}
            page = client.list_suppressed_destinations(**kwargs)
            emails |= {d['EmailAddress'].lower() for d in page['SuppressedDestinationSummaries']}
            token = page.get('NextToken')
            if not token:
                return emails
    except Exception as e:
        logger.warning('SES suppression list уншиж чадсангүй: %s', e)
        return set()


def campaign_blacklist(with_ses=True):
    """{шалтгаан: олонлог} — шалтгаан бүрээр (давхцалтай) тоолж харуулахад хэрэгтэй."""
    from emails.models import EmailBounce, EmailRecipient

    soft = Counter(norm_email(e) for e in EmailBounce.objects.filter(
        bounce_type='soft').values_list('email', flat=True))
    sources = {
        'blocked': blocked_emails(),
        'soft_bounce': {e for e, c in soft.items() if e and c >= SOFT_BOUNCE_LIMIT},
        'bounced': {norm_email(e) for e in EmailRecipient.objects.filter(
            status='bounced').values_list('email', flat=True)},
        'failed': {norm_email(e) for e in EmailRecipient.objects.filter(
            status='failed').values_list('email', flat=True)},
        'system': set(SYSTEM_EMAILS),
    }
    if with_ses:
        sources['ses_suppressed'] = ses_suppressed_emails()
    return {k: v - {''} for k, v in sources.items()}


def campaign_blocked_emails(with_ses=True):
    return set().union(*campaign_blacklist(with_ses).values())
