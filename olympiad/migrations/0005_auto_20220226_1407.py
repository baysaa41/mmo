# Generated by Django 3.1.6 on 2022-02-26 06:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('olympiad', '0004_auto_20220131_1821'),
    ]

    operations = [
        migrations.AddField(
            model_name='upload',
            name='is_official',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='upload',
            name='upload_time',
            field=models.DateTimeField(auto_created=True, default='2022-02-26 00:00:00'),
        ),
    ]
