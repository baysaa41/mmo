"""
Импортын командуудын хамгаалалт (mmo-system-accounts/ТӨЛӨВЛӨГӨӨ.md, 7 хоног 1):
- Олон нэр дэвшигч таарвал эхнийхийг АВАХГҮЙ — мөрийг review-д гаргана.
- Шинэ түр бүртгэл (placeholder) зөвхөн сургууль нь тодорхой үед үүснэ («Бусад» тооцохгүй).
"""


class NeedsReview(Exception):
    """Мөрийг автоматаар шийдэхгүй, хүн шалгана."""


def pick_unique(candidates, what='нэр дэвшигч'):
    candidates = list(candidates)
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        return None
    ids = ', '.join(str(u.pk) for u in candidates[:10])
    raise NeedsReview(f'{len(candidates)} {what} таарсан (ID: {ids}) — эхнийхийг сонгохгүй')


def require_school(school):
    if school is None or (getattr(school, 'name', '') or '').strip() == 'Бусад':
        raise NeedsReview('сургууль тодорхойгүй — шинэ түр бүртгэл үүсгэхгүй')
    return school


def record_review(command, reason, **row):
    entry = {'reason': str(reason), **row}
    if not isinstance(getattr(command, 'stats', None), dict):
        command.stats = {}
    command.stats.setdefault('needs_review', []).append(entry)
    command.stdout.write(command.style.WARNING(f"      🔎 REVIEW: {row.get('name', '')} — {reason}"))


def print_review_summary(command):
    rows = (getattr(command, 'stats', None) or {}).get('needs_review') or []
    if not rows:
        return
    command.stdout.write(command.style.WARNING(f'\n🔎 Хүн шалгах мөр (дүн оруулаагүй): {len(rows)}'))
    for r in rows:
        command.stdout.write(f"   - {r.get('name', '')} (ID: {r.get('id', 'N/A')}, аймаг: {r.get('province_id', '')}): {r['reason']}")
