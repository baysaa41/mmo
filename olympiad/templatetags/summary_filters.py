from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Dictionary-ээс key-ээр утга авах
    Хэрэглээ: {{ dict|get_item:key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, 0)
    return 0


@register.filter
def sum_level(summary_data, level_name):
    """
    Бүх аймгийн тухайн түвшин (level)-ийн оролцогчдын нийлбэрийг тооцоолох
    """
    total = 0
    for data in summary_data:
        levels = data.get('levels', {})
        total += levels.get(level_name, 0)
    return total


@register.filter
def sum_total(summary_data):
    """
    Бүх аймгийн нийт оролцогчдын нийлбэрийг тооцоолох
    """
    total = 0
    for data in summary_data:
        total += data.get('total', 0)
    return total
