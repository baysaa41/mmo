from django.db import migrations

# Хуучин мэдээнүүд (2015-2025) сүүлд нөхөж оруулсан тул хичээлийн жилийг нь
# өөрчлөхгүй, зөвхөн 2026-08-01-ний шинэ жилийн эхлэлээс хойшхи мэдээг л засна.
CORRECTIONS = [
    (490, 62, 63),
]


def set_correct_year(apps, schema_editor):
    Post = apps.get_model('posts', 'Post')
    for post_id, old_year_id, new_year_id in CORRECTIONS:
        Post.objects.filter(pk=post_id, year_id=old_year_id).update(year_id=new_year_id)


def set_old_year(apps, schema_editor):
    Post = apps.get_model('posts', 'Post')
    for post_id, old_year_id, new_year_id in CORRECTIONS:
        Post.objects.filter(pk=post_id, year_id=new_year_id).update(year_id=old_year_id)


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0004_post_attachments'),
        ('olympiad', '0008_fix_school_year_dates'),
    ]

    operations = [
        migrations.RunPython(set_correct_year, set_old_year),
    ]
