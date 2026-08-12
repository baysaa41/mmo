from django.db import migrations


def set_new_dates(apps, schema_editor):
    SchoolYear = apps.get_model('olympiad', 'SchoolYear')
    for school_year in SchoolYear.objects.all():
        if school_year.start:
            school_year.start = school_year.start.replace(month=8, day=1)
        if school_year.end:
            school_year.end = school_year.end.replace(month=7, day=31)
        school_year.save(update_fields=['start', 'end'])


def set_old_dates(apps, schema_editor):
    SchoolYear = apps.get_model('olympiad', 'SchoolYear')
    for school_year in SchoolYear.objects.all():
        if school_year.start:
            school_year.start = school_year.start.replace(month=8, day=31)
        if school_year.end:
            school_year.end = school_year.end.replace(month=8, day=31)
        school_year.save(update_fields=['start', 'end'])


class Migration(migrations.Migration):

    dependencies = [
        ('olympiad', '0007_add_is_problems_confidential'),
    ]

    operations = [
        migrations.RunPython(set_new_dates, set_old_dates),
    ]
