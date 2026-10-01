from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from olympiad.models import Olympiad, OlympiadGroup, Problem, Result


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
