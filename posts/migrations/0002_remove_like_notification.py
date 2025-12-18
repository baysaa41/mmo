# Generated manually to remove Like and Notification models

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0001_initial'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Like',
        ),
        migrations.DeleteModel(
            name='Notification',
        ),
    ]
