import os
import pandas as pd
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Өгсөн фолдерт байгаа Excel файлуудаас түлхүүр үг хайх'

    def add_arguments(self, parser):
        parser.add_argument(
            '--folder',
            type=str,
            required=True,
            help='Excel файлууд байрлах фолдерын зам'
        )
        parser.add_argument(
            '--keyword',
            type=str,
            required=True,
            help='Хайх түлхүүр үг'
        )
        parser.add_argument(
            '--case-sensitive',
            action='store_true',
            help='Том жижиг үсгийг ялгах (default: ялгахгүй)'
        )

    def handle(self, *args, **options):
        folder_path = options['folder']
        keyword = options['keyword']
        case_sensitive = options['case_sensitive']

        if not os.path.isdir(folder_path):
            raise CommandError(f"Фолдер олдсонгүй: {folder_path}")

        self.stdout.write(self.style.NOTICE(f"'{folder_path}' фолдерт '{keyword}' түлхүүр үгийг хайж байна..."))
        self.stdout.write("")

        total_files = 0
        total_matches = 0
        files_with_matches = []

        # Фолдер доторх бүх файлуудыг шалгах
        for filename in sorted(os.listdir(folder_path)):
            if not filename.endswith(('.xlsx', '.xls')):
                continue

            file_path = os.path.join(folder_path, filename)
            total_files += 1

            file_matches = 0

            try:
                # Excel файлын бүх sheet-ийг уншиж шалгах
                excel_file = pd.ExcelFile(file_path)

                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)

                    # DataFrame-ийг string болгож хайлт хийх
                    for row_idx, row in df.iterrows():
                        for col_name, cell_value in row.items():
                            if pd.isna(cell_value):
                                continue

                            cell_str = str(cell_value)

                            # Хайлт хийх
                            found = False
                            if case_sensitive:
                                found = keyword in cell_str
                            else:
                                found = keyword.lower() in cell_str.lower()

                            if found:
                                file_matches += 1
                                total_matches += 1

                                # Олдсон утгыг хэвлэх
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"  ✓ {filename} → {sheet_name} → Мөр {row_idx + 2}, Багана '{col_name}': {cell_str[:100]}"
                                    )
                                )

                if file_matches > 0:
                    files_with_matches.append((filename, file_matches))

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ {filename} файлыг уншихад алдаа гарлаа: {e}")
                )

        # Эцсийн тайлан
        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("📊 ХАЙЛТЫН ҮР ДҮН"))
        self.stdout.write("=" * 80)
        self.stdout.write(f"📁 Фолдер: {os.path.abspath(folder_path)}")
        self.stdout.write(f"🔍 Түлхүүр үг: '{keyword}'")
        self.stdout.write(f"📄 Нийт шалгасан файл: {total_files}")
        self.stdout.write(f"✅ Олдсон файлын тоо: {len(files_with_matches)}")
        self.stdout.write(f"🎯 Нийт олдсон: {total_matches}")

        if files_with_matches:
            self.stdout.write("")
            self.stdout.write("Файл бүрийн тоо:")
            for filename, count in files_with_matches:
                self.stdout.write(f"  • {filename}: {count} олдлоо")

        self.stdout.write("=" * 80)
