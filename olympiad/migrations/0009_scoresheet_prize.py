# Generated by Django 4.1.6 on 2024-12-17 22:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('olympiad', '0008_scoresheet_ranking_a_p_scoresheet_ranking_b_p'),
    ]

    operations = [
        migrations.AddField(
            model_name='scoresheet',
            name='prize',
            field=models.CharField(blank=True, max_length=256, null=True),
        ),
    ]
