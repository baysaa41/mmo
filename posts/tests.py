from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(
    MAINTENANCE_MODE=False,
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
              'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
)
class StaticPagesTests(TestCase):
    def test_pages_render_and_link_each_other(self):
        for name, heading in [('about', 'Бидний тухай'), ('terms', 'Үйлчилгээний нөхцөл'),
                              ('privacy', 'Нууцлалын бодлого')]:
            response = self.client.get(reverse(name))
            self.assertContains(response, heading)
            self.assertContains(response, reverse('terms'))
