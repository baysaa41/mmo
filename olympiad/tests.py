from django.test import SimpleTestCase, TestCase


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
