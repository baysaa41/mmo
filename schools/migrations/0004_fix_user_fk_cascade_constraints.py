from django.db import migrations

# models.py-д on_delete=CASCADE гэж заасан ч бодит DB constraint нь
# NO ACTION хэвээр байсан талбарыг загварт нийцүүлж CASCADE болгоно.

class Migration(migrations.Migration):

    dependencies = [
        ('schools', '0003_school_official_levels'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                'ALTER TABLE schools_uploadedexcel DROP CONSTRAINT schools_uploadedexcel_uploaded_by_id_d75f8393_fk_auth_user_id;\n'
                'ALTER TABLE schools_uploadedexcel ADD CONSTRAINT schools_uploadedexcel_uploaded_by_id_d75f8393_fk_auth_user_id '
                'FOREIGN KEY (uploaded_by_id) REFERENCES auth_user (id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;'
            ),
            reverse_sql=(
                'ALTER TABLE schools_uploadedexcel DROP CONSTRAINT schools_uploadedexcel_uploaded_by_id_d75f8393_fk_auth_user_id;\n'
                'ALTER TABLE schools_uploadedexcel ADD CONSTRAINT schools_uploadedexcel_uploaded_by_id_d75f8393_fk_auth_user_id '
                'FOREIGN KEY (uploaded_by_id) REFERENCES auth_user (id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;'
            ),
        ),
    ]
