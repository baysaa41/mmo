from django.core.cache import cache
from django.core.files.storage import default_storage

CACHE_KEY = 'timeline_series_file_sizes'


def series_file_sizes():
    """S3-ийн tsuvral/ хавтсан дахь цувралуудын {url: байт} — нэг list хүсэлтээр
    авч 1 цаг cache-лэнэ. Гадны (Google Drive г.м.) холбоосын хэмжээ гарахгүй."""
    sizes = cache.get(CACHE_KEY)
    if sizes is None:
        try:
            sizes = {
                default_storage.url(obj.key): obj.size
                for obj in default_storage.bucket.objects.filter(Prefix='tsuvral/')
            }
        except Exception:
            return {}
        cache.set(CACHE_KEY, sizes, 60 * 60)
    return sizes
