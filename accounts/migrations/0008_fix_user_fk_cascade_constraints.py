from django.db import migrations

# models.py-д on_delete=CASCADE гэж заасан ч бодит DB constraint нь
# RESTRICT/NO ACTION хэвээр байсан талбаруудыг загварт нийцүүлж CASCADE болгоно
# (deferrability-г хуучин constraint-тэй адил хэвээр үлдээв).

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_add_usermails_tracking_fields'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                'ALTER TABLE accounts_author DROP CONSTRAINT accounts_author_user_id_266b3ba5_fk_auth_user_id;\n'
                'ALTER TABLE accounts_author ADD CONSTRAINT accounts_author_user_id_266b3ba5_fk_auth_user_id '
                'FOREIGN KEY (user_id) REFERENCES auth_user (id) ON DELETE CASCADE;'
            ),
            reverse_sql=(
                'ALTER TABLE accounts_author DROP CONSTRAINT accounts_author_user_id_266b3ba5_fk_auth_user_id;\n'
                'ALTER TABLE accounts_author ADD CONSTRAINT accounts_author_user_id_266b3ba5_fk_auth_user_id '
                'FOREIGN KEY (user_id) REFERENCES auth_user (id) ON DELETE RESTRICT;'
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE accounts_teacherstudent DROP CONSTRAINT accounts_teacherstudent_student_id_c3aa64b7_fk_auth_user_id;\n'
                'ALTER TABLE accounts_teacherstudent ADD CONSTRAINT accounts_teacherstudent_student_id_c3aa64b7_fk_auth_user_id '
                'FOREIGN KEY (student_id) REFERENCES auth_user (id) ON DELETE CASCADE;'
            ),
            reverse_sql=(
                'ALTER TABLE accounts_teacherstudent DROP CONSTRAINT accounts_teacherstudent_student_id_c3aa64b7_fk_auth_user_id;\n'
                'ALTER TABLE accounts_teacherstudent ADD CONSTRAINT accounts_teacherstudent_student_id_c3aa64b7_fk_auth_user_id '
                'FOREIGN KEY (student_id) REFERENCES auth_user (id) ON DELETE RESTRICT;'
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE accounts_teacherstudent DROP CONSTRAINT accounts_teacherstudent_teacher_id_ab240425_fk_auth_user_id;\n'
                'ALTER TABLE accounts_teacherstudent ADD CONSTRAINT accounts_teacherstudent_teacher_id_ab240425_fk_auth_user_id '
                'FOREIGN KEY (teacher_id) REFERENCES auth_user (id) ON DELETE CASCADE;'
            ),
            reverse_sql=(
                'ALTER TABLE accounts_teacherstudent DROP CONSTRAINT accounts_teacherstudent_teacher_id_ab240425_fk_auth_user_id;\n'
                'ALTER TABLE accounts_teacherstudent ADD CONSTRAINT accounts_teacherstudent_teacher_id_ab240425_fk_auth_user_id '
                'FOREIGN KEY (teacher_id) REFERENCES auth_user (id) ON DELETE RESTRICT;'
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE accounts_uploadedfile DROP CONSTRAINT accounts_uploadedfile_uploaded_by_id_cbd0dd5b_fk_auth_user_id;\n'
                'ALTER TABLE accounts_uploadedfile ADD CONSTRAINT accounts_uploadedfile_uploaded_by_id_cbd0dd5b_fk_auth_user_id '
                'FOREIGN KEY (uploaded_by_id) REFERENCES auth_user (id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;'
            ),
            reverse_sql=(
                'ALTER TABLE accounts_uploadedfile DROP CONSTRAINT accounts_uploadedfile_uploaded_by_id_cbd0dd5b_fk_auth_user_id;\n'
                'ALTER TABLE accounts_uploadedfile ADD CONSTRAINT accounts_uploadedfile_uploaded_by_id_cbd0dd5b_fk_auth_user_id '
                'FOREIGN KEY (uploaded_by_id) REFERENCES auth_user (id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;'
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE accounts_usermeta DROP CONSTRAINT accounts_usermeta_user_id_bf7ac337_fk_auth_user_id;\n'
                'ALTER TABLE accounts_usermeta ADD CONSTRAINT accounts_usermeta_user_id_bf7ac337_fk_auth_user_id '
                'FOREIGN KEY (user_id) REFERENCES auth_user (id) ON DELETE CASCADE;'
            ),
            reverse_sql=(
                'ALTER TABLE accounts_usermeta DROP CONSTRAINT accounts_usermeta_user_id_bf7ac337_fk_auth_user_id;\n'
                'ALTER TABLE accounts_usermeta ADD CONSTRAINT accounts_usermeta_user_id_bf7ac337_fk_auth_user_id '
                'FOREIGN KEY (user_id) REFERENCES auth_user (id) ON DELETE RESTRICT;'
            ),
        ),
    ]
