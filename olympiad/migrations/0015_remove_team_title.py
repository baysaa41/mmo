# Generated by Django 3.1.6 on 2022-04-10 19:08

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('olympiad', '0014_auto_20220411_0302'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='team',
            name='title',
        ),
    ]
