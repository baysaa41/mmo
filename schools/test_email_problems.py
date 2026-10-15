from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Province, UserMeta
from emails.models import EmailBounce, EmailUnsubscribe
from schools.models import School
from schools.moderator import school_email_problem_users


class EmailProblemsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.province = Province.objects.create(name='Аймаг А')
        cls.group = Group.objects.create(name='Сургууль А')
        cls.moderator = User.objects.create_user('mod', email='mod@gmail.com', password='x')
        cls.school = School.objects.create(
            name='Сургууль А', province=cls.province, group=cls.group, user=cls.moderator)
        cls.other_group = Group.objects.create(name='Сургууль Б')
        cls.other_school = School.objects.create(
            name='Сургууль Б', province=cls.province, group=cls.other_group)

        cls.bad = User.objects.create_user('bad', email='Bad@gmmail.com', password='x', last_name='Бат')
        cls.good = User.objects.create_user('good', email='good@gmail.com', password='x')
        cls.soft = User.objects.create_user('soft', email='soft@gmail.com', password='x')
        cls.unsub = User.objects.create_user('unsub', email='unsub@gmail.com', password='x')
        cls.elsewhere = User.objects.create_user('else', email='else@gmail.com', password='x')
        for u in (cls.bad, cls.good, cls.soft, cls.unsub):
            u.groups.add(cls.group)
            UserMeta.objects.get_or_create(user=u)
        cls.elsewhere.groups.add(cls.other_group)

        EmailBounce.objects.create(email='bad@gmmail.com', bounce_type='hard')
        EmailBounce.objects.create(email='soft@gmail.com', bounce_type='soft')
        EmailBounce.objects.create(email='else@gmail.com', bounce_type='hard')
        EmailUnsubscribe.objects.create(email='unsub@gmail.com', user=cls.unsub)

    def test_lists_only_hard_bounced_members_of_this_school(self):
        rows = school_email_problem_users(self.school)
        self.assertEqual([r['user'] for r in rows], [self.bad])
        self.assertEqual(rows[0]['suggestion'], 'Bad@gmail.com')
        self.assertEqual(rows[0]['bounce_type'], 'hard')

    def test_moderator_with_bounced_email_gets_role(self):
        EmailBounce.objects.create(email='mod@gmail.com', bounce_type='complaint')
        rows = {r['user'].username: r for r in school_email_problem_users(self.school)}
        self.assertEqual(rows['mod']['role'], 'Бүртгэгч багш')

    def test_moderator_sees_page_and_edit_link(self):
        self.client.force_login(self.moderator)
        resp = self.client.get(reverse('school_email_problems', args=[self.school.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Bad@gmmail.com')
        self.assertContains(resp, reverse('edit_user_in_group', args=[self.bad.pk]))
        self.assertNotContains(resp, 'good@gmail.com')
        self.assertNotContains(resp, 'else@gmail.com')

    def test_other_school_admin_is_denied(self):
        stranger = User.objects.create_user('stranger', email='s@gmail.com', password='x')
        self.client.force_login(stranger)
        resp = self.client.get(reverse('school_email_problems', args=[self.school.id]))
        self.assertNotContains(resp, 'Bad@gmmail.com')

    def test_anonymous_is_redirected_to_login(self):
        resp = self.client.get(reverse('school_email_problems', args=[self.school.id]))
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_shows_count(self):
        self.client.force_login(self.moderator)
        resp = self.client.get(reverse('school_dashboard', args=[self.school.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['email_problem_count'], 1)
        self.assertContains(resp, reverse('school_email_problems', args=[self.school.id]))
