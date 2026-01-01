from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group, Permission
from django.db import transaction
from accounts.models import Province, UserMeta
import pandas as pd
import os


class Command(BaseCommand):
    help = 'Аймаг/дүүргүүдийн боловсролын мэргэжилтнүүдийг Excel файлаас импортлоно'

    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='Excel файлын зам')
        parser.add_argument('--dry-run', action='store_true', help='Зөвхөн харах горим (өгөгдөл хадгалахгүй)')

    def handle(self, *args, **options):
        excel_file = options['excel_file']
        dry_run = options['dry_run']

        if not os.path.exists(excel_file):
            self.stdout.write(self.style.ERROR(f'❌ Файл олдсонгүй: {excel_file}'))
            return

        self.stdout.write(f'📂 Файл: {excel_file}')
        self.stdout.write(f'Горим: {"DRY RUN" if dry_run else "PRODUCTION"}')
        self.stdout.write('=' * 80)

        # Статистик
        stats = {
            'provinces_processed': 0,
            'contact_persons_set': 0,
            'admins_added': 0,
            'users_created': 0,
            'users_updated': 0,
            'errors': [],
        }

        # Excel уншах
        try:
            df = pd.read_excel(excel_file, sheet_name='Province Managers')
            self.stdout.write(self.style.SUCCESS(f'✅ Файл уншигдлаа: {len(df)} мөр'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Файл уншихад алдаа: {e}'))
            return

        # Хоосон мөрүүдийг хасах (бүх чухал багана хоосон)
        df_filtered = df[
            df['Овог'].notna() &
            (df['Овог'].astype(str).str.strip() != '')
        ].copy()

        self.stdout.write(f'📊 Бөглөгдсөн мөр: {len(df_filtered)}')
        self.stdout.write('')

        # Province бүрээр боловсруулах
        for province_id in df_filtered['Аймаг/Дүүргийн ID'].unique():
            province_rows = df_filtered[df_filtered['Аймаг/Дүүргийн ID'] == province_id]

            try:
                province = Province.objects.get(id=province_id)
            except Province.DoesNotExist:
                error_msg = f'Province ID {province_id} олдсонгүй'
                stats['errors'].append(error_msg)
                self.stdout.write(self.style.ERROR(f'  ❌ {error_msg}'))
                continue

            self.stdout.write(f'\n🏛️  {province.name} (ID: {province_id})')
            self.stdout.write('-' * 60)

            # Contact person болон admin-уудыг боловсруулах
            contact_person_user = None

            for idx, row in province_rows.iterrows():
                role = str(row.get('Үүрэг', '')).strip().lower()
                last_name = str(row.get('Овог', '')).strip()
                first_name = str(row.get('Нэр', '')).strip()
                email = str(row.get('Имэйл', '')).strip()

                # "Хэрэглэгчийн ID" эсвэл хуучин "Холбоо барих хүний ID" багана хэрэглэх
                user_id = row.get('Хэрэглэгчийн ID')
                if pd.isna(user_id):
                    # Хуучин template-той нийцтэй байх
                    user_id = row.get('Холбоо барих хүний ID') if role == 'contact' else None

                if not last_name or not first_name or not email:
                    continue

                # Хэрэглэгч олох эсвэл үүсгэх
                user = None

                # 1. user_id байвал хайх
                if pd.notna(user_id):
                    try:
                        user = User.objects.get(id=int(user_id))
                        self.stdout.write(f'  ✓ Хэрэглэгч олдлоо: {user.username} (ID: {user.id})')
                    except User.DoesNotExist:
                        pass

                # 2. Email-ээр хайх
                if not user:
                    user = User.objects.filter(email=email).first()
                    if user:
                        self.stdout.write(f'  ✓ Email-ээр олдлоо: {user.username} ({email})')

                # 3. Үүсгэх
                if not user:
                    username = email.split('@')[0]
                    base_username = username
                    counter = 1

                    # Уникал username үүсгэх
                    while User.objects.filter(username=username).exists():
                        username = f"{base_username}{counter}"
                        counter += 1

                    if not dry_run:
                        user = User.objects.create_user(
                            username=username,
                            email=email,
                            first_name=first_name,
                            last_name=last_name,
                            password=User.objects.make_random_password(length=12)
                        )
                        stats['users_created'] += 1
                        self.stdout.write(self.style.SUCCESS(f'  ✅ Хэрэглэгч үүслээ: {username} ({email})'))

                        # UserMeta үүсгэх
                        UserMeta.objects.get_or_create(
                            user=user,
                            defaults={
                                'reg_num': '',
                                'province': province,
                            }
                        )
                    else:
                        self.stdout.write(f'  [DRY RUN] Үүсгэх: {username} ({email})')

                if user:
                    # UserMeta шалгах ба province тохируулах
                    if not dry_run:
                        meta, created = UserMeta.objects.get_or_create(user=user)
                        if not meta.province:
                            meta.province = province
                            meta.save(update_fields=['province'])
                            stats['users_updated'] += 1

                    # Role-ээр ажиллах
                    if role == 'contact':
                        contact_person_user = user
                        if not dry_run:
                            province.contact_person = user
                            province.save(update_fields=['contact_person'])
                            stats['contact_persons_set'] += 1
                            self.stdout.write(self.style.SUCCESS(f'  👤 Contact person: {user.username}'))
                        else:
                            self.stdout.write(f'  [DRY RUN] Contact person: {user.username}')

                    elif role == 'admin':
                        # Province admin group-т нэмэх
                        if not dry_run:
                            group_name = f'Province_{province_id}_Managers'
                            group, _ = Group.objects.get_or_create(name=group_name)

                            # edit_province permission олгох (Province model-ийн permission)
                            from django.contrib.contenttypes.models import ContentType
                            try:
                                province_ct = ContentType.objects.get_for_model(Province)
                                perm = Permission.objects.get(
                                    codename='edit_province',
                                    content_type=province_ct
                                )
                                group.permissions.add(perm)
                            except Permission.DoesNotExist:
                                pass

                            # Хэрэглэгчийг group-т нэмэх
                            user.groups.add(group)
                            stats['admins_added'] += 1
                            self.stdout.write(self.style.SUCCESS(f'  👥 Admin нэмэгдлээ: {user.username}'))
                        else:
                            self.stdout.write(f'  [DRY RUN] Admin: {user.username}')

            stats['provinces_processed'] += 1

        # Эцсийн тайлан
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('📊 ЭЦСИЙН ТАЙЛАН'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Горим: {"DRY RUN (Өгөгдөл хадгалаагүй)" if dry_run else "PRODUCTION (Өгөгдөл хадгалагдсан)"}')
        self.stdout.write(f'\n✅ Боловсруулсан province: {stats["provinces_processed"]}')
        self.stdout.write(f'👤 Contact person тохируулсан: {stats["contact_persons_set"]}')
        self.stdout.write(f'👥 Admin нэмэгдсэн: {stats["admins_added"]}')
        self.stdout.write(f'✨ Шинэ хэрэглэгч үүссэн: {stats["users_created"]}')
        self.stdout.write(f'🔄 Хэрэглэгч шинэчлэгдсэн: {stats["users_updated"]}')

        if stats['errors']:
            self.stdout.write(f'\n❌ Алдаанууд ({len(stats["errors"])}):')
            for err in stats['errors']:
                self.stdout.write(f'  - {err}')

        self.stdout.write('=' * 80)
