# Generated by Django 3.1.6 on 2022-04-03 06:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('olympiad', '0009_auto_20220325_1324'),
    ]

    operations = [
        migrations.AlterField(
            model_name='article',
            name='Descr',
            field=models.TextField(blank=True, null=True),
        ),
    ]
