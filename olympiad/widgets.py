from django.forms.widgets import ClearableFileInput
from django.utils.translation import gettext_lazy as _

class MultiFileInput(ClearableFileInput):
    allow_multiple_selected = True

    def __init__(self, attrs=None):
        attrs = attrs or {}
        if attrs.get('multiple'):
            attrs['multiple'] = 'multiple'
        super().__init__(attrs)

    def format_value(self, value):
        return [super().format_value(v) for v in value]