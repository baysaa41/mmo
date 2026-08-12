from django.db import migrations

# models.py-д on_delete=CASCADE гэж заасан ч бодит DB constraint нь
# NO ACTION хэвээр байсан талбаруудыг загварт нийцүүлж CASCADE болгоно.

class Migration(migrations.Migration):

    dependencies = [
        ('file_management', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                'ALTER TABLE file_management_fileaccesslog DROP CONSTRAINT file_management_fileaccesslog_user_id_c34b4b10_fk_auth_user_id;\n'
                'ALTER TABLE file_management_fileaccesslog ADD CONSTRAINT file_management_fileaccesslog_user_id_c34b4b10_fk_auth_user_id '
                'FOREIGN KEY (user_id) REFERENCES auth_user (id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;'
            ),
            reverse_sql=(
                'ALTER TABLE file_management_fileaccesslog DROP CONSTRAINT file_management_fileaccesslog_user_id_c34b4b10_fk_auth_user_id;\n'
                'ALTER TABLE file_management_fileaccesslog ADD CONSTRAINT file_management_fileaccesslog_user_id_c34b4b10_fk_auth_user_id '
                'FOREIGN KEY (user_id) REFERENCES auth_user (id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;'
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE file_management_fileupload DROP CONSTRAINT file_management_fileupload_uploader_id_138cf1c4_fk_auth_user_id;\n'
                'ALTER TABLE file_management_fileupload ADD CONSTRAINT file_management_fileupload_uploader_id_138cf1c4_fk_auth_user_id '
                'FOREIGN KEY (uploader_id) REFERENCES auth_user (id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;'
            ),
            reverse_sql=(
                'ALTER TABLE file_management_fileupload DROP CONSTRAINT file_management_fileupload_uploader_id_138cf1c4_fk_auth_user_id;\n'
                'ALTER TABLE file_management_fileupload ADD CONSTRAINT file_management_fileupload_uploader_id_138cf1c4_fk_auth_user_id '
                'FOREIGN KEY (uploader_id) REFERENCES auth_user (id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;'
            ),
        ),
    ]
