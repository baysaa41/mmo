from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from olympiad.models import SchoolYear
from .models import FileAccessLog, FileUpload

TEST_STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


@override_settings(STORAGES=TEST_STORAGES)
class TrainingMaterialTests(TestCase):
    def setUp(self):
        self.year = SchoolYear.objects.create(name='2025-2026')
        self.staff = User.objects.create_user(username='staff', password='pw', is_staff=True)
        self.student = User.objects.create_user(username='student', password='pw')
        self.material = FileUpload.objects.create(
            file=SimpleUploadedFile('egmo.pdf', b'%PDF-1.4 egmo'),
            kind=FileUpload.Kind.TRAINING,
            title='EGMO бэлтгэл 2026',
            teachers='Б. Батбаясгалан, Т. Хулан',
            uploader=self.staff,
            school_year=self.year,
        )
        self.general = FileUpload.objects.create(
            file=SimpleUploadedFile('guide.pdf', b'%PDF-1.4 guide'),
            description='Нууц заавар',
            uploader=self.staff,
            school_year=self.year,
        )

    def test_teacher_list_splits_names(self):
        self.assertEqual(self.material.teacher_list, ['Б. Батбаясгалан', 'Т. Хулан'])

    def test_list_page_is_public_and_shows_only_training(self):
        response = self.client.get(reverse('training_materials'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'EGMO бэлтгэл 2026')
        self.assertContains(response, 'Т. Хулан')
        self.assertNotContains(response, 'Нууц заавар')

    def test_any_logged_in_user_can_download_training_material(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('download_file', args=[self.material.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'%PDF-1.4 egmo')
        self.assertEqual(FileAccessLog.objects.filter(file=self.material, user=self.student).count(), 1)

    def test_anonymous_download_redirects_to_login(self):
        response = self.client.get(reverse('download_file', args=[self.material.id]))
        self.assertEqual(response.status_code, 302)

    def test_regular_user_still_cannot_download_general_file(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('download_file', args=[self.general.id]))
        self.assertNotIn('attachment', response.get('Content-Disposition', ''))

    def test_general_file_list_excludes_training(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('file_list'), {'year': self.year.id})
        self.assertEqual(list(response.context['files']), [self.general])

    def test_only_staff_can_upload(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('upload_training_material'))
        self.assertEqual(response.status_code, 302)

    def test_staff_upload_creates_training_material(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('upload_training_material'), {
            'title': 'IMO бэлтгэл 2026',
            'teachers': 'Ү. Отгонбаяр, Б. Билэгдэмбэрэл',
            'school_year': self.year.id,
            'description': '',
            'file': SimpleUploadedFile('imo.pdf', b'%PDF-1.4 imo'),
        })
        self.assertRedirects(response, reverse('training_materials'), fetch_redirect_response=False)
        created = FileUpload.objects.get(title='IMO бэлтгэл 2026')
        self.assertEqual(created.kind, FileUpload.Kind.TRAINING)
        self.assertEqual(created.uploader, self.staff)

    def test_only_staff_can_edit(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('edit_file', args=[self.general.id]))
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, reverse('file_list'))

    def test_staff_sees_edit_links(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('file_list'), {'year': self.year.id})
        self.assertContains(response, reverse('edit_file', args=[self.general.id]))
        response = self.client.get(reverse('training_materials'))
        self.assertContains(response, reverse('edit_file', args=[self.material.id]))

    def test_non_staff_does_not_see_edit_links(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('training_materials'))
        self.assertNotContains(response, reverse('edit_file', args=[self.material.id]))

    def test_edit_training_metadata_keeps_file(self):
        self.client.force_login(self.staff)
        old_name = self.material.file.name
        response = self.client.post(reverse('edit_file', args=[self.material.id]), {
            'title': 'EGMO бэлтгэл 2026 (засвар)',
            'teachers': 'Т. Хулан',
            'school_year': self.year.id,
            'description': 'Комбинаторик',
        })
        self.assertRedirects(response, reverse('training_materials'), fetch_redirect_response=False)
        self.material.refresh_from_db()
        self.assertEqual(self.material.title, 'EGMO бэлтгэл 2026 (засвар)')
        self.assertEqual(self.material.teacher_list, ['Т. Хулан'])
        self.assertEqual(self.material.file.name, old_name)
        self.assertEqual(self.material.kind, FileUpload.Kind.TRAINING)

    def test_edit_general_file_replaces_file(self):
        self.client.force_login(self.staff)
        old_name = self.general.file.name
        response = self.client.post(reverse('edit_file', args=[self.general.id]), {
            'description': 'Шинэ заавар',
            'school_year': self.year.id,
            'file': SimpleUploadedFile('guide2.pdf', b'%PDF-1.4 new'),
        })
        self.assertRedirects(response, reverse('file_list'), fetch_redirect_response=False)
        self.general.refresh_from_db()
        self.assertEqual(self.general.description, 'Шинэ заавар')
        self.assertEqual(self.general.kind, FileUpload.Kind.GENERAL)
        self.assertNotEqual(self.general.file.name, old_name)
        self.assertFalse(self.general.file.storage.exists(old_name))
