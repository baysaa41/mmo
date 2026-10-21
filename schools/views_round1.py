"""I давааны имэйлийн нэвтрэлтгүй хувийн хуудас (schools.round1_links)."""
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from . import round1_links as links

MAX_ROWS = 50  # олон аккаунттай (багшийн) хаягт хуудас хэт урт болохгүй


def round1_info_view(request, token):
    email = links.read_token(token)
    if not email:
        return render(request, 'schools/round1/invalid.html', status=404)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'request':
            ids = request.POST.getlist('user_id')
            n = links.send_requests(email, [int(i) for i in ids if i.isdigit()] if ids else None)
            if n:
                messages.success(request, f'{n} хүсэлт сургуулийн бүртгэгч багшид илгээгдлээ. '
                                          'Багш батлахад таны бүртгэл баталгаажна.')
            else:
                messages.info(request, 'Илгээх шинэ хүсэлт алга.')
        elif action == 'merge':
            ids = [int(i) for i in request.POST.get('user_ids', '').split(',') if i.strip().isdigit()]
            from .email_bulk import anchor_uid
            req = links.request_merge(email, anchor_uid(token), ids)
            if req:
                messages.success(request, f'Нэгтгэх хүсэлт #{req.id} илгээгдлээ. Админ хянаж нэгтгэнэ.')
            else:
                messages.info(request, 'Энэ бүлгийн нэгтгэх хүсэлт аль хэдийн илгээгдсэн эсвэл олдсонгүй.')
        elif action == 'interests':
            links.set_interests(email, {f: request.POST.get(f) == '1' for f in links.INTERESTS})
            messages.success(request, 'Таны сонголт хадгалагдлаа.')
        elif action == 'unsubscribe':
            links.unsubscribe(email)
            messages.success(request, 'Танд цаашид мэдээллийн имэйл илгээхгүй.')
        return redirect('round1_info', token=token)

    users = list(links.accounts_for_email(email))
    pending_ids = links.pending_merge_ids()
    dup_groups = [{'users': g, 'ids': ','.join(str(u.pk) for u in sorted(g, key=lambda u: u.pk)),
                   'requested': bool({u.pk for u in g} & pending_ids)} for g in links.duplicate_groups(users)]
    rows = links.account_rows(users)
    counts = {}
    for _u, status in rows:
        counts[status] = counts.get(status, 0) + 1
    return render(request, 'schools/round1/info.html', {
        'token': token,
        'email': email,
        'rows': rows[:MAX_ROWS],
        'hidden_count': max(0, len(rows) - MAX_ROWS),
        'total': len(rows),
        'counts': counts,
        'interests': links.current_interests(users),
        'dup_groups': dup_groups,
        'S': {'registered': links.REGISTERED, 'requested': links.REQUESTED,
              'not_registered': links.NOT_REGISTERED, 'no_school': links.NO_SCHOOL},
    })


@csrf_exempt
def round1_unsubscribe_view(request, token):
    """GET: баталгаажуулах хуудас (имэйл сканнер GET-ээр юу ч өөрчилдөггүй). POST: unsubscribe.

    RFC 8058 List-Unsubscribe-Post (Gmail/Yahoo-гийн 1-click) POST-оор ирнэ.
    """
    email = links.read_token(token)
    if not email:
        return render(request, 'schools/round1/invalid.html', status=404)
    if request.method == 'POST':
        links.unsubscribe(email, reason='List-Unsubscribe (1-click)')
        if request.POST.get('confirm'):
            return render(request, 'schools/round1/unsubscribed.html', {'email': email})
        return HttpResponse('OK')
    return render(request, 'schools/round1/unsubscribe.html', {'email': email, 'token': token})


def interests_view(request, token):
    """Сонирхол асуух имэйлийн хуудас: ямар мэдээллийг mmo.mn / mathminds.club-аас авахаа сонгоно.

    Анхдагчаар бүгд сонгоогүй (тодорхой зөвшөөрөл). GET юу ч өөрчилдөггүй, хадгалалт POST-оор.
    """
    email = links.read_token(token)
    if not email:
        return render(request, 'schools/round1/invalid.html', status=404)
    if request.method == 'POST':
        links.set_interests(email, {f: request.POST.get(f) == '1' for f in links.INTERESTS})
        messages.success(request, 'Баярлалаа! Таны сонголтыг хадгаллаа.')
        return redirect('round1_interests', token=token)
    users = list(links.accounts_for_email(email))
    return render(request, 'schools/round1/interests.html', {
        'token': token, 'email': email, 'interests': links.current_interests(users),
        'answered': links.interests_answered(users)})
