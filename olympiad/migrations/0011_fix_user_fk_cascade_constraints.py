from django.db import migrations

# Эдгээр талбарууд загварт (models.py) on_delete=CASCADE гэж заасан ч,
# бодит DB constraint нь RESTRICT/NO ACTION хэвээр байсан (магадгүй хуучин
# migration зөв ALTER хийгдээгүйгээс). Иймд Django ORM-оор биш, шууд SQL-аар
# хэрэглэгч устгах үед FK зөрчил гарч байсан. Энэ migration нь DB constraint-ыг
# загварт нийцүүлж CASCADE болгоно (deferrability-г хуучин constraint-тэй адил хэвээр үлдээв).

class Migration(migrations.Migration):

    dependencies = [
        ('olympiad', '0010_alter_roundguideline_round'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                'ALTER TABLE olympiad_result DROP CONSTRAINT olympiad_result_contestant_id_11f9ae90_fk_auth_user_id;\n'
                'ALTER TABLE olympiad_result ADD CONSTRAINT olympiad_result_contestant_id_11f9ae90_fk_auth_user_id '
                'FOREIGN KEY (contestant_id) REFERENCES auth_user (id) ON DELETE CASCADE;'
            ),
            reverse_sql=(
                'ALTER TABLE olympiad_result DROP CONSTRAINT olympiad_result_contestant_id_11f9ae90_fk_auth_user_id;\n'
                'ALTER TABLE olympiad_result ADD CONSTRAINT olympiad_result_contestant_id_11f9ae90_fk_auth_user_id '
                'FOREIGN KEY (contestant_id) REFERENCES auth_user (id) ON DELETE RESTRICT;'
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE olympiad_scoresheet DROP CONSTRAINT olympiad_scoresheet_user_id_086cab9c_fk_auth_user_id;\n'
                'ALTER TABLE olympiad_scoresheet ADD CONSTRAINT olympiad_scoresheet_user_id_086cab9c_fk_auth_user_id '
                'FOREIGN KEY (user_id) REFERENCES auth_user (id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;'
            ),
            reverse_sql=(
                'ALTER TABLE olympiad_scoresheet DROP CONSTRAINT olympiad_scoresheet_user_id_086cab9c_fk_auth_user_id;\n'
                'ALTER TABLE olympiad_scoresheet ADD CONSTRAINT olympiad_scoresheet_user_id_086cab9c_fk_auth_user_id '
                'FOREIGN KEY (user_id) REFERENCES auth_user (id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;'
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE olympiad_comment DROP CONSTRAINT olympiad_comment_author_id_d5ec6ca9_fk_auth_user_id;\n'
                'ALTER TABLE olympiad_comment ADD CONSTRAINT olympiad_comment_author_id_d5ec6ca9_fk_auth_user_id '
                'FOREIGN KEY (author_id) REFERENCES auth_user (id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;'
            ),
            reverse_sql=(
                'ALTER TABLE olympiad_comment DROP CONSTRAINT olympiad_comment_author_id_d5ec6ca9_fk_auth_user_id;\n'
                'ALTER TABLE olympiad_comment ADD CONSTRAINT olympiad_comment_author_id_d5ec6ca9_fk_auth_user_id '
                'FOREIGN KEY (author_id) REFERENCES auth_user (id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;'
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE olympiad_award DROP CONSTRAINT olympiad_award_contestant_id_dc369808_fk_auth_user_id;\n'
                'ALTER TABLE olympiad_award ADD CONSTRAINT olympiad_award_contestant_id_dc369808_fk_auth_user_id '
                'FOREIGN KEY (contestant_id) REFERENCES auth_user (id) ON DELETE CASCADE;'
            ),
            reverse_sql=(
                'ALTER TABLE olympiad_award DROP CONSTRAINT olympiad_award_contestant_id_dc369808_fk_auth_user_id;\n'
                'ALTER TABLE olympiad_award ADD CONSTRAINT olympiad_award_contestant_id_dc369808_fk_auth_user_id '
                'FOREIGN KEY (contestant_id) REFERENCES auth_user (id) ON DELETE RESTRICT;'
            ),
        ),
    ]
