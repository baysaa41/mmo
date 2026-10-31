from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from olympiad.management.commands.first_to_second_by_school_quota import (
    select_school_students,
)
from olympiad.models import Award, Olympiad, OlympiadGroup, Problem, Result, ScoreSheet, SchoolYear


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    MAINTENANCE_MODE=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class OlympiadGroupResultViewTests(TestCase):
    """pandas 3 + django-pandas read_frame-ийн TypeError-ийн регресс."""

    @classmethod
    def setUpTestData(cls):
        olympiad = Olympiad.objects.create(name='Туршилтын олимпиад')
        p1 = Problem.objects.create(olympiad=olympiad, order=1)
        p2 = Problem.objects.create(olympiad=olympiad, order=2)
        cls.group = Group.objects.create(name='Оролцогчид')
        cls.og = OlympiadGroup.objects.create(name='Нэгдсэн', group=cls.group)
        cls.og.olympiads.add(olympiad)

        cls.winner = User.objects.create_user('winner', first_name='Тэмүүлэн', last_name='Бат')
        cls.other = User.objects.create_user('other', first_name='Номин', last_name='Дорж')
        cls.group.user_set.add(cls.winner, cls.other)
        Result.objects.create(contestant=cls.winner, olympiad=olympiad, problem=p1, score=7)
        Result.objects.create(contestant=cls.winner, olympiad=olympiad, problem=p2, score=5)
        Result.objects.create(contestant=cls.other, olympiad=olympiad, problem=p1, score=3)
        Result.objects.create(contestant=cls.other, olympiad=olympiad, problem=p2, score=None)

    def test_group_results_render_sorted_by_total(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse('olympiad_group_result_view', args=[self.og.id]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Тэмүүлэн', html)
        self.assertIn('Номин', html)
        self.assertLess(html.index('Тэмүүлэн'), html.index('Номин'))


class ClassifyStatementTests(SimpleTestCase):
    """classify_problems командын түлхүүр үгийн ангиллын регресс."""

    def cat(self, statement):
        from olympiad.management.commands.classify_problems import classify_statement
        return classify_statement(statement)[0]

    def test_log_substring_does_not_mean_algebra(self):
        # "лог" нь "бодлого", "олонлог", "параллелограмм" дотроос таарч байсан
        self.assertIsNone(self.cat('Бодлого №3'))
        self.assertEqual(self.cat(
            '$ABCD$ параллелограммын $BD$ диагонал дээр $K$ цэг авав. '
            '$AK$ шулуун $CD$ шулууныг $M$ цэгт огтолно.'), 'GEO')
        self.assertEqual(self.cat(
            '$\\{1,2,\\dots,n\\}$ олонлогийн дэд олонлогийн тоог хэдэн янзаар сонгох вэ?'), 'COM')

    def test_perfect_square_is_number_theory(self):
        self.assertEqual(self.cat(
            '$4^{18}+4^{1000}+4^n$ тоог бүтэн квадрат байлгах хамгийн их натурал тоо $n$-ийг ол.'), 'NUM')

    def test_geometric_progression_is_not_geometry(self):
        self.assertNotEqual(self.cat(
            'Нийлбэр нь $832$ байх ба квадратууд нь геометр прогресс үүсгэх бүх натурал тоон гурвалыг ол.'), 'GEO')

    def test_inequality_is_algebra(self):
        self.assertEqual(self.cat(
            'Эерэг $a, b, c$ тоонуудын хувьд $a+b+c=3$ бол '
            '\\[\\dfrac{a+b}{2ab+1}+\\dfrac{b+c}{2bc+1}\\ge2\\] тэнцэтгэл биш биелэхийг батал.'), 'ALG')


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    MAINTENANCE_MODE=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class ProblemVisibilityBeforeFinishTests(TestCase):
    """Дуусаагүй олимпиадын бодлогын нөхцөл staff/координатороос бусдад задрахгүй."""

    @classmethod
    def setUpTestData(cls):
        from datetime import timedelta
        from django.utils import timezone
        now = timezone.now()
        cls.upcoming = Olympiad.objects.create(
            name='Удахгүй', start_time=now + timedelta(days=30),
            end_time=now + timedelta(days=30, hours=2))
        cls.finished = Olympiad.objects.create(
            name='Дууссан', start_time=now - timedelta(days=30),
            end_time=now - timedelta(days=30) + timedelta(hours=2))
        cls.secret = Problem.objects.create(
            olympiad=cls.upcoming, order=1, statement='НУУЦ_НӨХЦӨЛ')
        cls.public = Problem.objects.create(
            olympiad=cls.finished, order=1, statement='НЭЭЛТТЭЙ_НӨХЦӨЛ')
        cls.student = User.objects.create_user('student', password='x')
        cls.staff = User.objects.create_user('staff', password='x', is_staff=True)
        cls.coord = User.objects.create_user('coord', password='x')
        cls.secret.coordinators.add(cls.coord)

    def topics_html(self):
        response = self.client.get(reverse('problem_list_with_topics'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_topic_list_hides_unfinished_for_anonymous_and_students(self):
        for user in (None, self.student):
            if user:
                self.client.force_login(user)
            html = self.topics_html()
            self.assertNotIn('НУУЦ_НӨХЦӨЛ', html)
            self.assertIn('НЭЭЛТТЭЙ_НӨХЦӨЛ', html)

    def test_topic_list_search_does_not_leak(self):
        response = self.client.get(reverse('problem_list_with_topics'), {'q': 'НУУЦ'})
        self.assertNotIn('НУУЦ_НӨХЦӨЛ', response.content.decode())

    def test_topic_list_shows_unfinished_to_staff_and_coordinator(self):
        for user in (self.staff, self.coord):
            self.client.force_login(user)
            self.assertIn('НУУЦ_НӨХЦӨЛ', self.topics_html())

    def test_problem_stats_forbidden_before_finish(self):
        self.client.force_login(self.student)
        url = reverse('problem_stats', kwargs={'problem_id': self.secret.id})
        self.assertEqual(self.client.get(url).status_code, 403)
        url = reverse('olympiad_problem_stats', kwargs={'olympiad_id': self.upcoming.id})
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_problem_stats_allowed_after_finish_and_for_staff(self):
        self.client.force_login(self.student)
        url = reverse('problem_stats', kwargs={'problem_id': self.public.id})
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.staff)
        url = reverse('problem_stats', kwargs={'problem_id': self.secret.id})
        self.assertEqual(self.client.get(url).status_code, 200)


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    MAINTENANCE_MODE=False,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class RoundLedgerPlacementTests(TestCase):
    """Квотын дэвтэр round=1 хуудсанд, Хотын эрхийн дэвтэр round=2 хуудсанд байх ёстой."""

    @classmethod
    def setUpTestData(cls):
        from datetime import date, timedelta
        from olympiad.models import SchoolYear
        today = date.today()
        cls.year = SchoolYear.objects.create(
            name='2099-2100', start=today - timedelta(days=30), end=today + timedelta(days=30))

    def page(self, round):
        response = self.client.get(reverse('olympiad_round_detail', kwargs={'round': round}))
        self.assertEqual(response.status_code, 200)
        return response

    def test_round2_quota_ledger_is_on_round1_page(self):
        self.assertContains(self.page(1), reverse('round2_quota_summary'))

    def test_round2_page_no_longer_has_round2_quota_ledger(self):
        self.assertNotContains(self.page(2), reverse('round2_quota_summary'))

    def test_capital_ledger_is_on_round2_page(self):
        self.assertContains(self.page(2), reverse('round3_district_quota'))

    def test_round3_page_no_longer_has_capital_ledger(self):
        response = self.page(3)
        self.assertNotContains(response, reverse('round3_district_quota'))
        self.assertNotContains(response, 'Хотын эрхийн дэвтэр')

    def test_round1_page_does_not_have_capital_ledger(self):
        self.assertNotContains(self.page(1), reverse('round3_district_quota'))

    def test_ledger_breadcrumbs_point_to_the_new_pages(self):
        round1 = reverse('olympiad_round_detail', kwargs={'round': 1})
        round2 = reverse('olympiad_round_detail', kwargs={'round': 2})
        self.assertContains(self.client.get(reverse('round2_quota_summary')), round1)
        self.assertContains(self.client.get(reverse('round2_school_quota')), round1)
        self.assertContains(self.client.get(reverse('round3_district_quota')), round2)


class SelectSchoolStudentsTests(SimpleTestCase):
    """Сургууль × ангиллын квотын сонголтын цэвэр логик."""

    @staticmethod
    def rows(scores):
        return [
            {'user_id': i + 1, 'total': score, 'last_name': chr(0x410 + i), 'first_name': ''}
            for i, score in enumerate(scores)
        ]

    def ids(self, picked):
        return [r['user_id'] for r in picked]

    def test_exact_fills_quota_and_breaks_tie_by_name(self):
        picked = select_school_students(self.rows([5, 4, 4, 4]), 3, 'exact')
        self.assertEqual(self.ids(picked), [1, 2, 3])

    def test_fewer_drops_whole_boundary_tie_group(self):
        picked = select_school_students(self.rows([5, 4, 4, 4]), 3, 'fewer')
        self.assertEqual(self.ids(picked), [1])

    def test_more_includes_whole_boundary_tie_group(self):
        picked = select_school_students(self.rows([5, 4, 4, 4]), 3, 'more')
        self.assertEqual(self.ids(picked), [1, 2, 3, 4])

    def test_no_tie_takes_exactly_quota(self):
        picked = select_school_students(self.rows([9, 8, 7, 6]), 2)
        self.assertEqual(self.ids(picked), [1, 2])

    def test_fewer_participants_than_quota_takes_all(self):
        picked = select_school_students(self.rows([3, 1]), 5)
        self.assertEqual(self.ids(picked), [1, 2])

    def test_zero_quota_selects_nothing(self):
        self.assertEqual(select_school_students(self.rows([3, 1]), 0), [])


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    MAINTENANCE_MODE=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class FirstToSecondBySchoolQuotaCommandTests(TestCase):
    """first_to_second_by_school_quota команд: Award, prizes, групп."""

    @classmethod
    def setUpTestData(cls):
        from datetime import date, timedelta
        from accounts.models import Level, Province
        from schools.models import School

        cls.year = SchoolYear.objects.create(
            name='2099-2100',
            start=date.today() - timedelta(days=30),
            end=date.today() + timedelta(days=30),
        )
        cls.level = Level.objects.create(name='C (5-6)')
        cls.province = Province.objects.create(name='Аймаг А')
        cls.school = School.objects.create(name='Сургууль А', province=cls.province)

        cls.round1 = Olympiad.objects.create(
            name='I даваа', round=1, school_year=cls.year, level=cls.level)
        cls.round2 = Olympiad.objects.create(
            name='II даваа I шат', round=2, school_year=cls.year, level=cls.level)
        cls.round1.next_round = cls.round2
        cls.round1.save(update_fields=['next_round'])

        # 5 оролцогч: 5, 4, 3, 2, 1 оноо + 0 оноотой нэг (хасагдах ёстой)
        cls.students = []
        for i, (last_name, score) in enumerate(
            [('А', 5), ('Б', 4), ('В', 3), ('Г', 2), ('Д', 1), ('Е', 0)]
        ):
            user = User.objects.create_user(
                username=f'student{i}', first_name='Сурагч', last_name=last_name)
            ScoreSheet.objects.create(
                user=user, school=cls.school, olympiad=cls.round1,
                is_official=True, s1=score)
            cls.students.append(user)

    def quota_table(self, province, round2_olympiad):
        return {
            'round1_olympiads': Olympiad.objects.filter(next_round=round2_olympiad),
            'base_quota_per_school': 2,
            'historical_topn': 20,
            'region_type': 'Аймаг',
            'year_ids': [],
            'year_names': [],
            'year_columns': [],
            'total_B': 0,
            'schools_data': [{
                'school': self.school,
                'round1_participants': 5,
                'base_quota': 2,
                'yearly_counts': [0, 0, 0],
                'additional_quota': 1,
                'total_quota': 3,
                'new_yearly_counts': [0, 0, 0],
                'new_total_A': 0,
                'new_additional_quota': 0,
                'new_total_quota': 2,
            }],
            'total_round1_participants': 5,
            'total_base': 2,
            'total_yearly_counts': [0, 0, 0],
            'total_additional': 1,
            'total_quota': 3,
            'total_new_A_sum': 0,
            'total_new_additional': 0,
            'total_new_quota': 2,
        }

    def run_command(self, **kwargs):
        import io
        from unittest import mock

        out = io.StringIO()
        with mock.patch(
            'olympiad.management.commands.first_to_second_by_school_quota.'
            'compute_school_quota_table',
            side_effect=self.quota_table,
        ):
            call_command(
                'first_to_second_by_school_quota', year=self.year.id, stdout=out, **kwargs)
        return out.getvalue()

    def test_saves_awards_prizes_and_group(self):
        self.run_command()

        awards = list(
            Award.objects.filter(olympiad=self.round1)
            .order_by('contestant__last_name')
            .values_list('contestant__last_name', 'place')
        )
        # 5, 4, 3 оноотой эхний 3 (сургуулийн дотоод эрэмбээр), бүгд нэг нэртэй
        self.assertEqual(awards, [
            ('А', '2.1 эрх сургуулиас'),
            ('Б', '2.1 эрх сургуулиас'),
            ('В', '2.1 эрх сургуулиас'),
        ])

        # 0 оноотой сурагч сонгогдохгүй
        self.assertFalse(Award.objects.filter(contestant=self.students[3]).exists())
        self.assertFalse(Award.objects.filter(contestant=self.students[4]).exists())
        self.assertFalse(Award.objects.filter(contestant=self.students[5]).exists())

        self.round2.refresh_from_db()
        group_usernames = set(self.round2.group.user_set.values_list('username', flat=True))
        self.assertEqual(group_usernames, {'student0', 'student1', 'student2'})

        self.assertEqual(
            ScoreSheet.objects.get(olympiad=self.round1, user=self.students[2]).prizes,
            '2.1 эрх сургуулиас')

    def test_rerun_is_idempotent(self):
        self.run_command()
        self.run_command()
        self.assertEqual(Award.objects.filter(olympiad=self.round1).count(), 3)
        prizes = ScoreSheet.objects.get(
            olympiad=self.round1, user=self.students[2]).prizes
        self.assertEqual(prizes, '2.1 эрх сургуулиас')

    def test_default_tie_policy_is_fewer(self):
        # 5, 4, 4, 4, 1, 0 — квотын зааг (3-р байр) дээр тэнцэл үүснэ.
        ScoreSheet.objects.filter(
            olympiad=self.round1, user=self.students[2]).update(s1=4, total=4)
        ScoreSheet.objects.filter(
            olympiad=self.round1, user=self.students[3]).update(s1=4, total=4)

        self.run_command()

        # "тэнцвэл цөөнийг сонгоно" — 4 оноотой бүлэг бүтнээрээ хасагдаж, зөвхөн 5 оноотой сурагч үлдэнэ.
        self.assertEqual(
            list(Award.objects.filter(olympiad=self.round1).values_list(
                'contestant__username', flat=True)),
            ['student0'])

    def test_dry_run_saves_nothing(self):
        self.run_command(dry_run=True)
        self.assertFalse(Award.objects.filter(olympiad=self.round1).exists())
        self.round2.refresh_from_db()
        self.assertIsNone(self.round2.group)
