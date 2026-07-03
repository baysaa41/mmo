import os

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "MEDIA_ROOT доторх одоо байгаа файлуудыг AWS S3 (эсвэл settings.py-д "
        "тохируулсан S3Boto3Storage) руу upload хийнэ."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Файл руу юу ч бичихгүйгээр зөвхөн юу хийхийг харуулна.',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='S3 дээр аль хэдийн байгаа файлыг дахин upload хийж дарна.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        overwrite = options['overwrite']

        storage_module = default_storage.__class__.__module__
        if not storage_module.startswith('storages.backends.s3'):
            self.stderr.write(self.style.ERROR(
                f"DEFAULT_FILE_STORAGE нь S3 storage биш байна "
                f"(одоогийн: {storage_module}.{default_storage.__class__.__name__}). "
                "settings.py-г шалгана уу."
            ))
            return

        media_root = str(settings.MEDIA_ROOT)
        if not os.path.isdir(media_root):
            self.stderr.write(self.style.ERROR(f"MEDIA_ROOT олдсонгүй: {media_root}"))
            return

        try:
            default_storage.exists('__upload_media_to_s3_preflight_check__')
        except ClientError as exc:
            raise CommandError(
                f"S3-тэй холбогдож чадсангүй (bucket: {settings.AWS_STORAGE_BUCKET_NAME}, "
                f"region: {settings.AWS_S3_REGION_NAME}). AWS credentials болон bucket нэрийг "
                f"settings.py-с шалгана уу.\nАлдаа: {exc}"
            )

        uploaded = 0
        skipped = 0
        failed = 0

        for dirpath, _dirnames, filenames in os.walk(media_root):
            for filename in filenames:
                local_path = os.path.join(dirpath, filename)
                relative_path = os.path.relpath(local_path, media_root).replace(os.sep, '/')

                try:
                    exists_on_s3 = default_storage.exists(relative_path)
                except ClientError as exc:
                    self.stderr.write(self.style.ERROR(f"АЛДАА ({relative_path}): {exc}"))
                    failed += 1
                    continue

                if exists_on_s3 and not overwrite:
                    self.stdout.write(f"SKIP (байгаа): {relative_path}")
                    skipped += 1
                    continue

                if dry_run:
                    action = 'OVERWRITE' if exists_on_s3 else 'UPLOAD'
                    self.stdout.write(f"[dry-run] {action}: {relative_path}")
                    uploaded += 1
                    continue

                try:
                    if exists_on_s3:
                        default_storage.delete(relative_path)
                    with open(local_path, 'rb') as fh:
                        default_storage.save(relative_path, File(fh))
                    self.stdout.write(self.style.SUCCESS(f"OK: {relative_path}"))
                    uploaded += 1
                except Exception as exc:
                    self.stderr.write(self.style.ERROR(f"АЛДАА ({relative_path}): {exc}"))
                    failed += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nДууслаа. Upload: {uploaded}, Skip: {skipped}, Алдаа: {failed}"
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING("Энэ бол --dry-run горим байсан тул бодит upload хийгдээгүй."))
