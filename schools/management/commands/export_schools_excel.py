from django.core.management.base import BaseCommand
from schools.models import School
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
import os


class Command(BaseCommand):
    help = 'Сургуулиудын нэр, ID бүхий Excel файл үүсгэх. Дүүрэг тус бүр тусдаа sheet дээр.'

    def handle(self, *args, **kwargs):
        # Excel workbook үүсгэх
        wb = Workbook()
        # Анхдагч sheet-ийг устгах
        wb.remove(wb.active)

        # Сургуулиудыг дүүргээр нь бүлэглэх
        schools_by_province = {}
        schools = School.objects.select_related('province').all()

        for school in schools:
            province_name = school.province.name if school.province else 'Аймаг/Дүүрэггүй'

            if province_name not in schools_by_province:
                schools_by_province[province_name] = []

            schools_by_province[province_name].append(school)

        # Дүүрэг тус бүрийн хувьд sheet үүсгэх
        for province_name in sorted(schools_by_province.keys()):
            # Sheet нэр нь 31 тэмдэгтээс хэтрэхгүй байх ёстой
            sheet_name = province_name[:31]
            ws = wb.create_sheet(title=sheet_name)

            # Толгой мөр
            ws['A1'] = '№'
            ws['B1'] = 'ID'
            ws['C1'] = 'Сургуулийн нэр'
            ws['D1'] = 'Удирдлагын овог'
            ws['E1'] = 'Удирдлагын нэр'
            ws['F1'] = 'Удирдлагын имэйл'

            # Толгой мөрийг тодотгох
            for cell in ['A1', 'B1', 'C1', 'D1', 'E1', 'F1']:
                ws[cell].font = Font(bold=True)
                ws[cell].alignment = Alignment(horizontal='center', vertical='center')

            # Сургуулиудыг нэрээр нь эрэмбэлэх
            schools_list = sorted(schools_by_province[province_name], key=lambda s: s.name)

            # Өгөгдөл оруулах
            for idx, school in enumerate(schools_list, start=1):
                row = idx + 1
                ws[f'A{row}'] = idx
                ws[f'B{row}'] = school.id
                ws[f'C{row}'] = school.name

                # Удирдлагын мэдээлэл - хоосон үлдээх (цуглуулах зорилгоор)
                ws[f'D{row}'] = ''
                ws[f'E{row}'] = ''
                ws[f'F{row}'] = ''

                # Дугаарыг төвлөрүүлэх
                ws[f'A{row}'].alignment = Alignment(horizontal='center')
                ws[f'B{row}'].alignment = Alignment(horizontal='center')

            # Баганын өргөнийг тохируулах
            ws.column_dimensions['A'].width = 8
            ws.column_dimensions['B'].width = 10
            ws.column_dimensions['C'].width = 60
            ws.column_dimensions['D'].width = 20
            ws.column_dimensions['E'].width = 20
            ws.column_dimensions['F'].width = 30

        # Файлыг хадгалах
        output_file = 'schools_by_province.xlsx'
        wb.save(output_file)

        self.stdout.write(
            self.style.SUCCESS(f'Амжилттай! Файл үүсгэгдлээ: {os.path.abspath(output_file)}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Нийт дүүрэг/аймаг: {len(schools_by_province)}')
        )

        total_schools = sum(len(schools) for schools in schools_by_province.values())
        self.stdout.write(
            self.style.SUCCESS(f'Нийт сургууль: {total_schools}')
        )
