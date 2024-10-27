# Generated by Django 4.1.6 on 2024-10-27 06:41

import ckeditor.fields
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import olympiad.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Olympiad',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('description', models.TextField(default='')),
                ('start_time', models.DateTimeField(blank=True, null=True)),
                ('end_time', models.DateTimeField(blank=True, null=True)),
                ('final_message', models.TextField(default='Бодлогууд таалагдсан гэдэгт итгэлтэй байна. Цаашид улам хичээн суралцаарай!')),
                ('is_open', models.BooleanField(default=True)),
                ('is_grading', models.BooleanField(default=False)),
                ('round', models.IntegerField(choices=[(0, 'Бусад олимпиад'), (1, 'Сонгон шалгаруулалт'), (2, 'Дүүргийн олимпиад'), (3, 'Хотын олимпиад'), (4, 'Улсын олимпиад'), (5, 'Олон улсын олимпиад'), (6, 'Олон улсын бусад')], default=0)),
                ('type', models.IntegerField(choices=[(0, 'Уламжлалт'), (1, 'Тест')], default=0)),
                ('month', models.IntegerField(blank=True, null=True)),
                ('num', models.IntegerField(default=1)),
                ('json_results', models.TextField(blank=True, null=True)),
                ('group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.group')),
                ('host', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.province')),
                ('level', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.level')),
                ('next_round', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='next', to='olympiad.olympiad')),
            ],
            options={
                'ordering': ['-school_year_id', '-id'],
            },
        ),
        migrations.CreateModel(
            name='Problem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField(default=1)),
                ('statement', models.TextField(blank=True, null=True)),
                ('max_score', models.IntegerField(default=7)),
                ('state', models.IntegerField(choices=[(0, 'Дэвшигдсэн'), (1, 'Сонгогдсон')], default=0)),
                ('type', models.IntegerField(choices=[(0, 'Уламжлалт'), (1, 'Сонгох'), (2, 'Нөхөх')], default=0)),
                ('numerical_answer', models.BigIntegerField(blank=True, null=True)),
                ('comments', models.TextField(blank=True, null=True)),
                ('author', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.author')),
                ('olympiad', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='olympiad.olympiad')),
            ],
            options={
                'permissions': [('edit_problem', 'Can edit problem')],
            },
        ),
        migrations.CreateModel(
            name='Result',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_grade', models.IntegerField(default=0)),
                ('answer', models.BigIntegerField(blank=True, null=True)),
                ('score', models.FloatField(blank=True, null=True)),
                ('grader_comment', models.TextField(blank=True, default='')),
                ('source_file', models.TextField(blank=True, default='')),
                ('state', models.IntegerField(choices=[(0, 'Хариулаагүй'), (1, 'Засагдаагүй'), (2, 'Урьдчилсан'), (3, 'Маргаантай'), (4, 'Зөвшөөрөгдсөн'), (5, 'Батлагдсан')], default=0)),
                ('date', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=False)),
                ('confirmed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='confirmed_results', to=settings.AUTH_USER_MODEL)),
                ('contestant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='contest_results', to=settings.AUTH_USER_MODEL)),
                ('coordinator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='coordinated_results', to=settings.AUTH_USER_MODEL)),
                ('olympiad', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='olympiad.olympiad')),
                ('problem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='olympiad.problem')),
            ],
            options={
                'permissions': [('edit_result', 'Дүн оруулах'), ('confirm_result', 'Дүн баталгаажуулах')],
            },
        ),
        migrations.CreateModel(
            name='Round',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('descr', models.TextField(blank=True, null=True)),
                ('is_official', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='SchoolYear',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=10, null=True)),
                ('start', models.DateField(blank=True, null=True)),
                ('end', models.DateField(blank=True, null=True)),
                ('descr', models.CharField(blank=True, max_length=100, null=True)),
            ],
            options={
                'ordering': ['-name'],
            },
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
            ],
        ),
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ranking', models.IntegerField(default=0)),
                ('province', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='teams', to='accounts.province')),
                ('schoolYear', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='olympiad.schoolyear')),
                ('zone', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='teams', to='accounts.zone')),
            ],
        ),
        migrations.CreateModel(
            name='Topic',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('ALG', 'Алгебр'), ('COM', 'Комбинаторик'), ('GEO', 'Геометр'), ('NUM', 'Тооны онол'), ('MIX', 'Хольмог')], default='ALG', max_length=3)),
                ('name', models.CharField(max_length=120)),
            ],
        ),
        migrations.CreateModel(
            name='Upload',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('upload_time', models.DateTimeField(auto_created=True, auto_now_add=True)),
                ('is_official', models.BooleanField(default=True)),
                ('file', models.ImageField(upload_to=olympiad.models.Upload.file_to)),
                ('result', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='olympiad.result')),
            ],
        ),
        migrations.CreateModel(
            name='Threshold',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('min_score', models.IntegerField(default=7)),
                ('olympiad', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='thresholds', to='olympiad.olympiad')),
                ('province', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.province')),
                ('zone', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.zone')),
            ],
        ),
        migrations.CreateModel(
            name='TeamMember',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ranking', models.IntegerField(default=0)),
                ('olympiad', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='olympiad.olympiad')),
                ('team', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='members', to='olympiad.team')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='teams', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Solution',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(null=True)),
                ('author', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('problem', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='olympiad.problem')),
            ],
            options={
                'permissions': [('edit_solution', 'Can edit solution')],
            },
        ),
        migrations.AddField(
            model_name='problem',
            name='topics',
            field=models.ManyToManyField(blank=True, to='olympiad.topic'),
        ),
        migrations.CreateModel(
            name='OlympiadGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('olympiads', models.ManyToManyField(blank=True, to='olympiad.olympiad')),
            ],
        ),
        migrations.AddField(
            model_name='olympiad',
            name='school_year',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='olympiad.schoolyear'),
        ),
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comment', models.TextField()),
                ('recommendation', models.FloatField(blank=True, null=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('result', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='olympiad.result')),
            ],
        ),
        migrations.CreateModel(
            name='Award',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('place', models.CharField(choices=[('Алт', 'Алтан медаль'), ('Мөнгө', 'Мөнгөн медаль'), ('Хүрэл', 'Хүрэл медаль'), ('Тусгай', 'Тусгай шагнал'), ('Уран бодолт', 'Уран бодолт'), ('I шат', 'I шат'), ('II шат', 'II шат')], default='Алт', max_length=128)),
                ('confirmed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='confirmed_awards', to=settings.AUTH_USER_MODEL)),
                ('contestant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('grade', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='awards', to='accounts.grade')),
                ('olympiad', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='awards', to='olympiad.olympiad')),
            ],
            options={
                'permissions': [('edit_award', 'Шагнал засах'), ('confirm_award', 'Шагнал баталгаажуулах')],
            },
        ),
        migrations.CreateModel(
            name='Article',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('oldid', models.IntegerField()),
                ('title', models.CharField(blank=True, max_length=500, null=True)),
                ('intro', models.TextField(blank=True, null=True)),
                ('descr', ckeditor.fields.RichTextField(blank=True, null=True)),
                ('startdate', models.DateField(blank=True, null=True)),
                ('enddate', models.DateField(blank=True, null=True)),
                ('imagesource', models.CharField(blank=True, max_length=200, null=True)),
                ('isspec', models.BooleanField(default=False)),
                ('embedcode', models.TextField(blank=True, null=True)),
                ('pictures', models.TextField(blank=True, null=True)),
                ('files', models.TextField(blank=True, null=True)),
                ('tags', models.TextField(blank=True, null=True)),
                ('sawcount', models.IntegerField(blank=True, null=True)),
                ('isshow', models.BooleanField(default=True)),
                ('createuserid', models.IntegerField(blank=True, null=True)),
                ('createdate', models.DateField(blank=True, null=True)),
                ('updatedate', models.DateField(blank=True, null=True)),
                ('author', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.author')),
                ('year', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='olympiad.schoolyear')),
            ],
            options={
                'ordering': ['-year_id', '-isspec'],
            },
        ),
        migrations.CreateModel(
            name='AnswerChoice',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField()),
                ('label', models.CharField(max_length=8)),
                ('value', models.TextField(default='')),
                ('points', models.IntegerField()),
                ('problem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='olympiad.problem')),
            ],
        ),
    ]
