# Generated by Django 4.1.6 on 2024-11-14 15:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('olympiad', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='olympiad',
            name='round',
            field=models.IntegerField(choices=[(0, 'Бусад олимпиад'), (1, 'Сургуулийн олимпиад'), (2, 'Дүүргийн олимпиад'), (3, 'Хотын олимпиад'), (4, 'Улсын олимпиад'), (5, 'Олон улсын олимпиад'), (6, 'Олон улсын бусад')], default=0),
        ),
    ]