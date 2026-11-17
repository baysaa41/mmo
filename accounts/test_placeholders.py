"""Системийн түр (placeholder) бүртгэлийн хамгаалалт — mmo-system-accounts, 7 хоног 1."""
from io import StringIO
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import Province, UserMeta
from olympiad.management.commands.universal_import import Command as UniversalImport
from olympiad.management.placeholder_guard import NeedsReview, pick_unique, require_school
from olympiad.models import Award
from schools.models import School


def make(username, email='', last_login=None, province=None, school=None, **kw):
    u = User.objects.create(username=username, email=email, last_login=last_login, **kw)
    UserMeta.objects.create(user=u, province=province, school=school)
    return u


def run(*args):
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


class MarkPlaceholdersTest(TestCase):
    def setUp(self):
        self.mmo60 = make('m1', email='mmo60official@gmail.com')
        self.auto = make('a1', email='auto-user@mmo.mn')
        self.noemail = make('n1')
        self.noemail_loggedin = make('n2', last_login=timezone.now())
        self.real = make('r1', email='real@gmail.com')
        self.staff = make('s1', is_staff=True)

    def flags(self):
        return dict(UserMeta.objects.filter(is_placeholder=True).values_list('user__username', 'placeholder_source'))

    def test_dry_run_changes_nothing(self):
        run('mark_placeholders')
        self.assertEqual(self.flags(), {})

    def test_apply_marks_only_system_accounts(self):
        run('mark_placeholders', '--apply')
        self.assertEqual(self.flags(), {'m1': 'mmo60', 'a1': 'auto_user', 'n1': 'no_email'})
        run('mark_placeholders', '--apply')  # дахин ажиллуулахад аюулгүй
        self.assertEqual(len(self.flags()), 3)


class DeletionGuardTest(TestCase):
    def setUp(self):
        self.placeholder = make('p1', email='auto-user@mmo.mn')
        UserMeta.objects.filter(user=self.placeholder).update(is_placeholder=True)
        self.with_award = make('p2', email='auto-user@mmo.mn')
        Award.objects.create(contestant=self.with_award)
        self.bare = make('p3', email='auto-user@mmo.mn')

    def test_delete_auto_users_spares_placeholders_and_data(self):
        out = run('delete_auto_users', '--confirm')
        self.assertIn('2 хэрэглэгч хамгаалагдсан', out)
        self.assertEqual(set(User.objects.values_list('username', flat=True)), {'p1', 'p2'})

    def test_delete_inactive_users_spares_award_holders(self):
        old = timezone.now() - timezone.timedelta(days=800)
        User.objects.update(last_login=old)
        UserMeta.objects.update(is_placeholder=False)
        run('delete_inactive_users', '--confirm')
        self.assertEqual(set(User.objects.values_list('username', flat=True)), {'p2'})


class ImportGuardTest(TestCase):
    def setUp(self):
        self.province = Province.objects.create(name='Аймаг')
        self.school = School.objects.create(name='Тэст сургууль', province=self.province,
                                            group=Group.objects.create(name='School_T'))
        self.busad = School.objects.create(name='Бусад', province=self.province)
        self.cmd = UniversalImport(stdout=StringIO(), stderr=StringIO())
        self.cmd.stats = {'users_created': 0, 'province_updated': 0, 'missing_groups': []}

    def test_pick_unique(self):
        a, b = make('x1'), make('x2')
        self.assertEqual(pick_unique([a]), a)
        self.assertIsNone(pick_unique([]))
        with self.assertRaises(NeedsReview):
            pick_unique([a, b])
        with self.assertRaises(NeedsReview):
            require_school(self.busad)
        self.assertEqual(require_school(self.school), self.school)

    def test_ambiguous_name_goes_to_review(self):
        for i in range(2):
            u = make(f'd{i}', province=self.province)
            User.objects.filter(pk=u.pk).update(last_name='Бат', first_name='Дорж')
        before = User.objects.count()
        user = self.cmd.get_user_smart(float('nan'), 'Бат', 'Дорж', 'Тэст сургууль', self.province.id)
        self.assertIsNone(user)
        self.assertEqual(User.objects.count(), before)
        self.assertIn('2 нэр дэвшигч', self.cmd.stats['needs_review'][0]['reason'])

    def test_unique_name_still_matches(self):
        u = make('solo', province=self.province)
        User.objects.filter(pk=u.pk).update(last_name='Ганаа', first_name='Сараа')
        self.assertEqual(self.cmd.get_user_smart(float('nan'), 'Ганаа', 'Сараа', None, self.province.id), u)

    def test_no_school_means_no_new_placeholder(self):
        before = User.objects.count()
        self.assertIsNone(self.cmd.get_user_smart(float('nan'), 'Шинэ', 'Сурагч', 'Огт байхгүй', self.province.id))
        self.assertIsNone(self.cmd.get_user_smart(float('nan'), 'Шинэ', 'Сурагч', None, self.province.id))
        self.assertEqual(User.objects.count(), before)
        self.assertEqual(len(self.cmd.stats['needs_review']), 2)

    def test_new_placeholder_with_school_is_flagged(self):
        user = self.cmd.get_user_smart(float('nan'), 'Шинэ', 'Сурагч', 'Тэст сургууль', self.province.id)
        self.assertIsNotNone(user)
        self.assertTrue(user.data.is_placeholder)
        self.assertEqual(user.data.placeholder_source, 'auto_user')
        self.assertEqual(user.data.school, self.school)
