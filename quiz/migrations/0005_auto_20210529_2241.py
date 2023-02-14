# Generated by Django 3.1.6 on 2021-05-29 14:41

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('quiz', '0004_quiz_quiz_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='result',
            name='comment',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='upload',
            name='uploaded',
            field=models.DateTimeField(auto_created=True, auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
