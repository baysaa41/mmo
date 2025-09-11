from django.db import migrations

def transfer_articles_to_posts(apps, schema_editor):
    try:
        Article = apps.get_model('olympiad', 'Article')
    except LookupError:
        # Хэрэв Article модел устгагдсан бол юу ч хийхгүй
        return

    Post = apps.get_model('posts', 'Post')

    # Өмнө нь өгөгдөл хуулсан бол дахин ажиллахаас сэргийлнэ
    if Post.objects.exists():
        return

    for article in Article.objects.all():
        Post.objects.create(
            # Хуучин болон шинэ моделын талбаруудыг нэг нэгээр нь онооно
            id=article.id,
            oldid=article.oldid,
            title=article.title,
            intro=article.intro,
            descr=article.descr,  # Хуучин descr талбарыг шинэ content руу хийнэ
            year_id=article.year_id,
            startdate=article.startdate,
            enddate=article.enddate,
            imagesource=article.imagesource,
            author_id=article.author_id,
            isspec=article.isspec,
            embedcode=article.embedcode,
            pictures=article.pictures,
            files=article.files,
            tags=article.tags,
            sawcount=article.sawcount,
            isshow=article.isshow,
            createuserid=article.createuserid,
            createdate=article.createdate,
            updatedate=article.updatedate
        )

class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0001_initial'),
        ('olympiad', '0001_initial'), # Энэ хэсэг таны olympiad-ийн сүүлийн migration-тай таарах ёстой
    ]

    operations = [
        migrations.RunPython(transfer_articles_to_posts, migrations.RunPython.noop),
    ]
