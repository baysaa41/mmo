import uuid

from django.db import migrations, models


# 0001_initial-д is_opened, tracking_token талбарууд хожим гараар нэмэгдсэн тул
# шинэ (хоосон) DB дээр энэ migration "column already exists" алдаа өгдөг байв.
# Одоо зөвхөн DB-д байхгүй баганыг нэмнэ. State-ийн хувьд 0001 эдгээрийг
# эцсийн хэлбэрээр нь аль хэдийн тодорхойлсон тул state operation хэрэггүй.

def add_missing_tracking_fields(apps, schema_editor):
    UserMails = apps.get_model('accounts', 'UserMails')
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        columns = {
            col.name for col in
            connection.introspection.get_table_description(cursor, UserMails._meta.db_table)
        }

    if 'is_opened' not in columns:
        schema_editor.add_field(UserMails, UserMails._meta.get_field('is_opened'))

    if 'tracking_token' not in columns:
        final_field = UserMails._meta.get_field('tracking_token')
        nullable_field = models.UUIDField(null=True, default=None)
        nullable_field.set_attributes_from_name('tracking_token')
        nullable_field.model = UserMails
        schema_editor.add_field(UserMails, nullable_field)
        for pk in UserMails.objects.values_list('pk', flat=True).iterator():
            UserMails.objects.filter(pk=pk).update(tracking_token=uuid.uuid4())
        schema_editor.alter_field(UserMails, nullable_field, final_field)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_add_zone_olympiads_m2m'),
    ]

    operations = [
        migrations.RunPython(add_missing_tracking_fields, migrations.RunPython.noop),
    ]
