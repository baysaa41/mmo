# Generated by Django 4.1.6 on 2024-12-17 22:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('olympiad', '0005_alter_article_year'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='scoresheet',
            name='prizes',
        ),
        migrations.RemoveField(
            model_name='scoresheet',
            name='ranking_a',
        ),
        migrations.RemoveField(
            model_name='scoresheet',
            name='ranking_a_p',
        ),
        migrations.RemoveField(
            model_name='scoresheet',
            name='ranking_b',
        ),
        migrations.RemoveField(
            model_name='scoresheet',
            name='ranking_b_p',
        ),
        migrations.AlterField(
            model_name='article',
            name='createdate',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='article',
            name='startdate',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='article',
            name='year',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='olympiad.schoolyear'),
        ),
        migrations.AlterField(
            model_name='olympiad',
            name='round',
            field=models.IntegerField(choices=[(0, 'Бусад олимпиад'), (1, 'Сонгон шалгаруулалт'), (2, 'Дүүргийн олимпиад'), (3, 'Хотын олимпиад'), (4, 'Улсын олимпиад'), (5, 'Олон улсын олимпиад'), (6, 'Олон улсын бусад')], default=0),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='olympiad',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='score_sheets', to='olympiad.olympiad'),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s1',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s10',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s11',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s12',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s13',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s14',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s15',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s16',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s17',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s18',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s19',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s2',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s20',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s3',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s4',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s5',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s6',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s7',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s8',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='scoresheet',
            name='s9',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
    ]
