# Generated manually to remove Like and Notification models

from django.db import migrations


def delete_tables_if_exist(apps, schema_editor):
    """
    Safely delete Like and Notification tables if they exist
    """
    from django.db import connection
    with connection.cursor() as cursor:
        # Get current schema
        cursor.execute("SELECT current_schema();")
        schema = cursor.fetchone()[0]

        # Check and drop posts_like table
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = %s
                AND table_name = 'posts_like'
            );
        """, [schema])
        if cursor.fetchone()[0]:
            cursor.execute("DROP TABLE posts_like CASCADE;")

        # Check and drop posts_notification table
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = %s
                AND table_name = 'posts_notification'
            );
        """, [schema])
        if cursor.fetchone()[0]:
            cursor.execute("DROP TABLE posts_notification CASCADE;")


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(delete_tables_if_exist, migrations.RunPython.noop),
    ]
