"""
Олон мөртэй хүснэгтэд (мөр бүрт `{% url %}`) reverse() дуудахад удаан тул, `<int:...>` ганц
параметртэй URL-ийн загварыг нэг удаа тооцоод ID-г нь л залгана.

    {% load fast_urls %}
    <a href="{% id_url 'edit_user_in_group' user.id %}">Засах</a>

`{% url 'edit_user_in_group' user.id %}`-тэй ижил үр дүн өгнө (нэг `<int:...>` параметртэй,
замын төгсгөлд байрлах URL-д л хэрэглэнэ).
"""
from django import template
from django.urls import reverse

register = template.Library()

_templates = {}


@register.simple_tag
def id_url(name, pk):
    pk = int(pk)
    parts = _templates.get(name)
    if parts is None:
        # 0 нь `<int:...>`-д таарна; төгсгөлийн `/0/`-оор тэмдэглэж, хоёр хэсэгт хуваана
        full = reverse(name, args=[0])
        prefix, sep, suffix = full.rpartition('/0/')
        if not sep:
            return reverse(name, args=[pk])
        parts = _templates[name] = (prefix, suffix)
    prefix, suffix = parts
    return f'{prefix}/{pk}/{suffix}'
