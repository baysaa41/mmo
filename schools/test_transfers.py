from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Province, UserMeta
from schools.models import EnrollmentLog, School, StudentTransfer
from schools.tests import TEST_STORAGES, make_user

Status = StudentTransfer.Status


@override_settings(
    STORAGES=TEST_STORAGES,
    MAINTENANCE_MODE=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class StudentTransferTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.province = Province.objects.create(name='Баянгол дүүрэг')
        cls.mod_a = make_user('mod_a', province=cls.province, email='a@example.com', first_name='Баасансүрэн')
        cls.mod_b = make_user('mod_b', province=cls.province, email='b@example.com')
        cls.mod_c = make_user('mod_c', province=cls.province)
        cls.school_a = School.objects.create(name='Оюуны Ундраа', province=cls.province, user=cls.mod_a,
                                             group=Group.objects.create(name='A'))
        cls.school_b = School.objects.create(name='22-р сургууль', province=cls.province, user=cls.mod_b,
                                             group=Group.objects.create(name='B'))
        cls.school_c = School.objects.create(name='Өөр', province=cls.province, user=cls.mod_c,
                                             group=Group.objects.create(name='C'))
        cls.students = []
        for i in range(3):
            u = make_user(f'st{i}', school=cls.school_a, province=cls.province, last_name='Овог', first_name=f'С{i}')
            u.groups.add(cls.school_a.group)
            cls.students.append(u)
        cls.outsider = make_user('outsider', school=cls.school_c, province=cls.province)
        cls.outsider.groups.add(cls.school_c.group)

    def _request(self, users, to_school=None):
        self.client.force_login(self.mod_a)
        return self.client.post(reverse('transfer_students', args=[self.school_a.id]), {
            'user_ids': [u.id for u in users],
            'to_school': (to_school or self.school_b).id,
            'note': 'сургууль хуваагдсан',
        })

    def test_request_creates_pending_and_keeps_student_in_old_school(self):
        r = self._request(self.students[:2])
        self.assertRedirects(r, reverse('school_transfers', args=[self.school_a.id]))
        self.assertEqual(StudentTransfer.objects.filter(status=Status.PENDING, to_school=self.school_b).count(), 2)
        self.assertTrue(self.students[0].groups.filter(pk=self.school_a.group_id).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['b@example.com'])
        self.assertTrue(mail.outbox[0].alternatives)  # HTML хувилбартай

    def test_cannot_transfer_students_of_other_school(self):
        self._request([self.outsider])
        self.assertFalse(StudentTransfer.objects.exists())

    def test_duplicate_pending_request_is_skipped(self):
        self._request(self.students[:1])
        self._request(self.students[:1], to_school=self.school_c)
        self.assertEqual(StudentTransfer.objects.filter(user=self.students[0]).count(), 1)

    def test_registrar_teacher_cannot_be_transferred(self):
        self.mod_a.groups.add(self.school_a.group)
        self._request([self.mod_a])
        self.assertFalse(StudentTransfer.objects.exists())

    def test_receiver_accepts(self):
        self._request(self.students)
        mail.outbox.clear()
        ids = list(StudentTransfer.objects.values_list('id', flat=True))
        self.client.force_login(self.mod_b)
        self.client.post(reverse('school_transfers', args=[self.school_b.id]),
                         {'action': 'accept', 'transfer_ids': ids[:2]})
        moved = [t.user for t in StudentTransfer.objects.filter(status=Status.ACCEPTED)]
        self.assertEqual(len(moved), 2)
        for u in moved:
            u.refresh_from_db()
            self.assertTrue(u.groups.filter(pk=self.school_b.group_id).exists())
            self.assertFalse(u.groups.filter(pk=self.school_a.group_id).exists())
            self.assertEqual(UserMeta.objects.get(user=u).school_id, self.school_b.id)
            self.assertTrue(EnrollmentLog.objects.filter(user=u, action='transfer', to_school=self.school_b).exists())
        self.assertEqual(StudentTransfer.objects.filter(status=Status.PENDING).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['a@example.com'])

    def test_receiver_rejects(self):
        self._request(self.students[:1])
        t = StudentTransfer.objects.get()
        self.client.force_login(self.mod_b)
        self.client.post(reverse('school_transfers', args=[self.school_b.id]),
                         {'action': 'reject', 'transfer_ids': [t.id]})
        t.refresh_from_db()
        self.assertEqual(t.status, Status.REJECTED)
        self.assertTrue(self.students[0].groups.filter(pk=self.school_a.group_id).exists())

    def test_sender_cannot_accept_own_request_and_can_cancel(self):
        self._request(self.students[:1])
        t = StudentTransfer.objects.get()
        url = reverse('school_transfers', args=[self.school_a.id])
        self.client.post(url, {'action': 'accept', 'transfer_ids': [t.id]})
        t.refresh_from_db()
        self.assertEqual(t.status, Status.PENDING)
        self.client.post(url, {'action': 'cancel', 'transfer_ids': [t.id]})
        t.refresh_from_db()
        self.assertEqual(t.status, Status.CANCELLED)

    def test_third_school_cannot_decide(self):
        self._request(self.students[:1])
        t = StudentTransfer.objects.get()
        self.client.force_login(self.mod_c)
        self.client.post(reverse('school_transfers', args=[self.school_c.id]),
                         {'action': 'accept', 'transfer_ids': [t.id]})
        t.refresh_from_db()
        self.assertEqual(t.status, Status.PENDING)
        r = self.client.post(reverse('school_transfers', args=[self.school_b.id]),
                             {'action': 'accept', 'transfer_ids': [t.id]})
        t.refresh_from_db()
        self.assertEqual(t.status, Status.PENDING)

    def test_pages_render(self):
        self._request(self.students[:1])
        self.client.force_login(self.mod_a)
        r = self.client.get(reverse('transfer_students', args=[self.school_a.id]),
                            {'user_ids': ','.join(str(u.id) for u in self.students)})
        self.assertContains(r, '22-р сургууль')
        self.assertContains(r, 'С2')
        r = self.client.get(reverse('school_all_users', args=[self.school_a.id]))
        self.assertContains(r, 'transferBtn')
        self.client.force_login(self.mod_b)
        r = self.client.get(reverse('school_dashboard', args=[self.school_b.id]))
        self.assertContains(r, 'шилжүүлэх хүсэлт ирсэн')
        r = self.client.get(reverse('school_transfers', args=[self.school_b.id]))
        self.assertContains(r, 'Сонгосныг хүлээн авах')
