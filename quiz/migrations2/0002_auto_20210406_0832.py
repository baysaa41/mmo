# Generated by Django 3.1.6 on 2021-04-06 08:32

from django.db import migrations, models
import django.db.models.deletion
import quiz.models


class Migration(migrations.Migration):

    dependencies = [
        ('quiz', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='result',
            name='score',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='answerchoice',
            name='points',
            field=models.IntegerField(default=2),
        ),
        migrations.AlterField(
            model_name='quiz',
            name='end_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='quiz',
            name='start_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='Upload',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.ImageField(upload_to=quiz.models.Upload.file_to)),
                ('result', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='quiz.result')),
            ],
        ),
    ]