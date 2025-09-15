from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def command_guide_view(request):
    """
    Админ хэрэглэгчдэд зориулсан, системийн тусгай коммандуудын
    тайлбар, заавар бүхий хуудсыг харуулна.
    """
    commands_data = [
        {
            'name': 'generate_answer_sheet',
            'description': 'Олимпиадын хариултыг бөглөхөд зориулсан, сурагчдын мэдээллээр урьдчилан дүүргэсэн Excel загвар файлыг үүсгэнэ. Файл нь 2 sheet-тэй, Монгол нэртэй багануудтай, хүрээтэй, цэгцтэй загвартай гарна.',
            'usage': 'python manage.py generate_answer_sheet --olympiad-id [ID] --school-id [ID] --output-file [ФАЙЛЫН ЗАМ]',
            'examples': [
                '# Хоосон загвар үүсгэх:',
                'python manage.py generate_answer_sheet --olympiad-id 55 --school-id 42 --output-file ./olymp55_school42.xlsx',
                '# Санамсаргүй хариултаар дүүргэсэн туршилтын файл үүсгэх:',
                'python manage.py generate_answer_sheet --olympiad-id 55 --school-id 42 --output-file ./test_olymp55.xlsx --test'
            ]
        },
        {
            'name': 'import_answers_from_excel',
            'description': 'Заасан хавтас доторх бүх Excel файлаас олимпиадын хариултыг уншиж, системд бөөнөөр импортолно. Импортлохын өмнө сурагчийн ID, овог нэр, сургуулийн харьяалал, хариултын формат зэргийг шалгана.',
            'usage': 'python manage.py import_answers_from_excel --directory [ХАВТАСНЫ ЗАМ]',
            'examples': [
                'python manage.py import_answers_from_excel --directory /home/deploy/answer_sheets/'
            ]
        },
        {
            'name': 'find_duplicate_users',
            'description': 'Системд давхардсан болон буруу форматтай регистрийн дугаартай хэрэглэгчдийг илрүүлж, жагсаалт харуулна. Энэ комманд мэдээллийн санд өөрчлөлт хийхгүй.',
            'usage': 'python manage.py find_duplicate_users',
            'examples': []
        },
        {
            'name': 'automerge_users',
            'description': 'Давхардсан хэрэглэгчдийг ухаалгаар нэгтгэнэ. --all горимд ажиллахдаа регистр, овог нэр таарсан хэрэглэгчдийг автоматаар, зөрсөн тохиолдолд асуулттайгаар нэгтгэнэ. Нэгтгэхээсээ өмнө дүнгийн зөрчлийг шалгадаг.',
            'usage': 'python manage.py automerge_users [--all | --reg-num [РЕГИСТР]]',
            'examples': [
                '# Бүх боломжит давхардлыг шалгах:',
                'python manage.py automerge_users --all',
                '# Зөвхөн тодорхой нэг регистрээр нэгтгэх:',
                'python manage.py automerge_users --reg-num УБ00112233'
            ]
        },
        {
            'name': 'advance_grades',
            'description': 'Хичээлийн жил дуусахад бүх сурагчдын ангийг нэгээр ахиулж, төгсөх ангийнхныг тохируулсан үүрэгт шилжүүлдэг.',
            'usage': 'python manage.py advance_grades',
            'examples': []
        },
        {
            'name': 'generate_scoresheets',
            'description': 'Олимпиадын дүн(Result)-г ашиглан нэгдсэн онооны хуудас (ScoreSheet)-г үүсгэж, улсын, аймгийн, бүсийн эрэмбийг тооцоолно.',
            'usage': 'python manage.py generate_scoresheets --olympiad-id [ID] [--force-delete]',
            'examples': [
                '# Онооны хуудас үүсгэх:',
                'python manage.py generate_scoresheets --olympiad-id 77',
                '# Хуучин оноог устгаад шинээр үүсгэх:',
                'python manage.py generate_scoresheets --olympiad-id 77 --force-delete'
            ]
        },
    ]
    context = {
        'commands': commands_data
    }
    return render(request, 'accounts/command_guide.html', context)