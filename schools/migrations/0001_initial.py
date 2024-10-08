# Generated by Django 5.0.6 on 2024-09-21 15:09

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Moderator',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='moderator', to='auth.group')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='moderating', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
