from django.db import migrations

# models.py-д on_delete=CASCADE гэж заасан ч бодит DB constraint нь
# NO ACTION хэвээр байсан талбаруудыг загварт нийцүүлж CASCADE болгоно.

class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0002_add_unique_per_email'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                'ALTER TABLE emails_emailcampaign DROP CONSTRAINT emails_emailcampaign_created_by_id_605412dc_fk_auth_user_id;\n'
                'ALTER TABLE emails_emailcampaign ADD CONSTRAINT emails_emailcampaign_created_by_id_605412dc_fk_auth_user_id '
                'FOREIGN KEY (created_by_id) REFERENCES auth_user (id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;'
            ),
            reverse_sql=(
                'ALTER TABLE emails_emailcampaign DROP CONSTRAINT emails_emailcampaign_created_by_id_605412dc_fk_auth_user_id;\n'
                'ALTER TABLE emails_emailcampaign ADD CONSTRAINT emails_emailcampaign_created_by_id_605412dc_fk_auth_user_id '
                'FOREIGN KEY (created_by_id) REFERENCES auth_user (id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;'
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE emails_emailunsubscribe DROP CONSTRAINT emails_emailunsubscribe_user_id_60c4074a_fk_auth_user_id;\n'
                'ALTER TABLE emails_emailunsubscribe ADD CONSTRAINT emails_emailunsubscribe_user_id_60c4074a_fk_auth_user_id '
                'FOREIGN KEY (user_id) REFERENCES auth_user (id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;'
            ),
            reverse_sql=(
                'ALTER TABLE emails_emailunsubscribe DROP CONSTRAINT emails_emailunsubscribe_user_id_60c4074a_fk_auth_user_id;\n'
                'ALTER TABLE emails_emailunsubscribe ADD CONSTRAINT emails_emailunsubscribe_user_id_60c4074a_fk_auth_user_id '
                'FOREIGN KEY (user_id) REFERENCES auth_user (id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;'
            ),
        ),
    ]
