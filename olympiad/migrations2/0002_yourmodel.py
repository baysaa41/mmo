# Generated by Django 4.1.6 on 2023-12-08 13:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('olympiad', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='YourModel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id_number', models.CharField(max_length=50, unique=True)),
                ('last_name', models.CharField(max_length=255)),
                ('first_name', models.CharField(max_length=255)),
                ('registration_number', models.CharField(max_length=50)),
                ('phone_number', models.CharField(max_length=20)),
                ('email', models.EmailField(max_length=254)),
                ('region_id', models.CharField(max_length=10)),
                ('school', models.CharField(max_length=255)),
                ('class_name', models.CharField(max_length=50)),
                ('is_attending_event', models.BooleanField(default=False)),
            ],
        ),
    ]