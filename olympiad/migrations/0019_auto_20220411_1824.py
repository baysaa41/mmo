# Generated by Django 3.1.6 on 2022-04-11 10:24

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('olympiad', '0018_auto_20220411_1017'),
    ]

    operations = [
        migrations.RenameField(
            model_name='teammember',
            old_name='place',
            new_name='ranking',
        ),
        migrations.RemoveField(
            model_name='teammember',
            name='grade',
        ),
        migrations.RemoveField(
            model_name='teammember',
            name='score',
        ),
        migrations.AddField(
            model_name='result',
            name='user_grade',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='teammember',
            name='olympiad',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='olympiad.olympiad'),
        ),
    ]
