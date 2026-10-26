"""
Хүргэгдэхгүй гэдэг нь мэдэгдсэн хаяг руу имэйл илгээхээс сэргийлэх, мөн
имэйл хаягийн домэйны бичгийн алдааг илрүүлэх.

Яагаад: SES-ийн bounce мэдэгдэл `EmailBounce`-д бүртгэгддэг ч зөвхөн кампанит
ажил (`emails/tasks.py`) үүнийг шалгадаг байв. Идэвхжүүлэх, нууц үг сэргээх,
сургуулийн имэйлүүд hard bounce хийсэн хаяг руу дахин дахин илгээгдэж, SES
дансны bounce хувийг өсгөж байсан.
"""
import logging

from django.core.exceptions import ValidationError

from .models import EmailBounce

logger = logging.getLogger(__name__)

# Хүргэгдэхгүй гэж үзэх bounce төрөл. `soft` (түр зуурын: хайрцаг дүүрсэн г.м.)
# ороогүй — тэр нь хожим засагдах боломжтой.
UNDELIVERABLE_BOUNCE_TYPES = ('hard', 'complaint')

# Монгол хэрэглэгчдийн хамгийн их алдах домэйнууд. Зөвхөн ТОДОРХОЙ алдааг
# жагсаасан — «тохирох ойролцоо домэйн» таах нь жинхэнэ домэйныг буруу
# татгалзах эрсдэлтэй. `gmail.ru`, `hmail.com` зэрэг өөр эзэнтэй байж болох
# домэйныг санаатайгаар оруулаагүй.
DOMAIN_TYPOS = {
    'gmmail.com': 'gmail.com',
    'gmial.com': 'gmail.com',
    'gamil.com': 'gmail.com',
    'gmai.com': 'gmail.com',
    'gmail.con': 'gmail.com',
    'gmail.cm': 'gmail.com',
    'gnail.com': 'gmail.com',
    'gemail.com': 'gmail.com',
    'gmail.comm': 'gmail.com',
    'ayhoo.com': 'yahoo.com',
    'yaho.com': 'yahoo.com',
    'yahooo.com': 'yahoo.com',
    'yahoo.con': 'yahoo.com',
    'hotmial.com': 'hotmail.com',
    'hotmail.con': 'hotmail.com',
    'outlok.com': 'outlook.com',
}


def _variants(email):
    email = (email or '').strip()
    return {email, email.lower()}


def is_undeliverable(email):
    """Энэ хаяг руу өмнө нь hard bounce эсвэл complaint ирсэн бол True."""
    variants = _variants(email)
    if not email or not email.strip():
        return False
    return EmailBounce.objects.filter(
        email__in=variants, bounce_type__in=UNDELIVERABLE_BOUNCE_TYPES
    ).exists()


def email_typo_suggestion(email):
    """Домэйн нь мэдэгдэж буй бичгийн алдаа бол зөв хаягийг, үгүй бол None буцаана."""
    local, sep, domain = (email or '').strip().rpartition('@')
    if not sep:
        return None
    fixed = DOMAIN_TYPOS.get(domain.lower())
    return f'{local}@{fixed}' if fixed else None


def validate_no_email_typo(email):
    """Django validator: мэдэгдэж буй домэйны алдаатай хаягийг татгалзана."""
    suggestion = email_typo_suggestion(email)
    if suggestion:
        raise ValidationError(
            'Имэйл хаягийн домэйн буруу байна. «%(suggestion)s» гэж бичих санаатай юу?',
            code='email_typo',
            params={'suggestion': suggestion},
        )
