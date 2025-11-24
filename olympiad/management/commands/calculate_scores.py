from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Тестийн олимпиадын оноог тооцох'

    def add_arguments(self, parser):
        parser.add_argument('olympiad_ids', nargs='+', type=int, help='Олимпиадын ID-ууд')

    def handle(self, *args, **options):
        olympiad_ids = options['olympiad_ids']
        ids_str = ','.join(map(str, olympiad_ids))

        self.stdout.write(f'Олимпиадууд: {olympiad_ids}')

        with connection.cursor() as cursor:
            # Зөв хариултын оноог тооцох (хоёр хариултын аль нэгийг шалгах)
            cursor.execute(f'''
                UPDATE olympiad_result r
                SET score = CASE
                    WHEN r.answer IS NOT NULL AND (
                        r.answer = p.numerical_answer OR
                        (p.numerical_answer2 IS NOT NULL AND r.answer = p.numerical_answer2)
                    )
                    THEN p.max_score
                    ELSE 0
                END
                FROM olympiad_problem p
                WHERE r.problem_id = p.id
                AND r.olympiad_id IN ({ids_str})
            ''')
            updated = cursor.rowcount

            # Статистик
            cursor.execute(f'''
                SELECT COUNT(*) FROM olympiad_result
                WHERE olympiad_id IN ({ids_str}) AND score > 0
            ''')
            correct = cursor.fetchone()[0]

        self.stdout.write(self.style.SUCCESS(
            f'Дууслаа! Зөв хариулт: {correct}, Шинэчлэгдсэн: {updated}'
        ))
