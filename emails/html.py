"""
Энгийн текст имэйлд HTML хувилбар нэмэх.

SES-ийн нээлт (open) хянах нь HTML дахь пиксел зургаар ажилладаг тул зөвхөн текст
илгээсэн имэйлийн нээлт бүртгэгддэггүй. text_email() нь текстийг HTML болгож
хавсаргасан EmailMultiAlternatives буцаана.
"""
import re

from django.core.mail import EmailMultiAlternatives
from django.utils.html import escape

_URL_RE = re.compile(r'(https?://[^\s<>«»"]+[^\s<>«»".,;:!?)\]])')


def text_to_html(text):
    """Мөр, догол мөрийг хадгалж, холбоосыг идэвхтэй болгосон энгийн HTML."""
    paragraphs = re.split(r'\n\s*\n', (text or '').strip())
    parts = []
    for p in paragraphs:
        html = _URL_RE.sub(r'<a href="\1">\1</a>', escape(p)).replace('\n', '<br>\n')
        parts.append(f'<p style="margin:0 0 12px">{html}</p>')
    return ('<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5;color:#222">'
            + '\n'.join(parts) + '</div>')


def text_email(subject, body, from_email, to, **kwargs):
    """Текст + автомат HTML хувилбартай имэйл. kwargs нь EmailMultiAlternatives-д дамжина."""
    msg = EmailMultiAlternatives(subject=subject, body=body, from_email=from_email, to=to, **kwargs)
    msg.attach_alternative(text_to_html(body), 'text/html')
    return msg
