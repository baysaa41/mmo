import uuid

from django.db import migrations, models


def backfill_tracking_tokens(apps, schema_editor):
    UserMails = apps.get_model('accounts', 'UserMails')
    for row in UserMails.objects.all().only('id').iterator():
        UserMails.objects.filter(pk=row.pk).update(tracking_token=uuid.uuid4())


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_add_zone_olympiads_m2m'),
    ]

    operations = [
        migrations.AddField(
            model_name='usermails',
            name='is_opened',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='usermails',
            name='tracking_token',
            field=models.UUIDField(null=True, default=None),
        ),
        migrations.RunPython(backfill_tracking_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='usermails',
            name='tracking_token',
            field=models.UUIDField(default=uuid.uuid4, unique=True),
        ),
    ]
