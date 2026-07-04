import json
import os

from django.contrib.auth.models import User
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from file_management.models import FileUpload
from posts.models import Post

IMPORT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', '_old_attachments_import')
MAPPING_PATH = os.path.join(IMPORT_DIR, 'mapping.json')
FILES_DIR = os.path.join(IMPORT_DIR, 'files')


class Command(BaseCommand):
    help = (
        'One-time import of old-mmo article attachments (uni_files) into '
        'file_management.FileUpload, linked to the matching migrated Post via '
        'Post.files (comma-separated legacy FileIDs).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--uploader', default='baysa',
            help='Username to record as the uploader of imported files.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would happen without writing to the DB or storage.',
        )

    def handle(self, *args, **options):
        if not os.path.isfile(MAPPING_PATH):
            raise CommandError(f'Mapping file not found: {MAPPING_PATH}')

        with open(MAPPING_PATH, encoding='utf-8') as f:
            mapping = json.load(f)

        dry_run = options['dry_run']
        uploader = User.objects.get(username=options['uploader'])

        posts = Post.objects.filter(files__isnull=False).exclude(files='')
        total_posts = 0
        total_linked = 0
        total_missing = 0
        skipped_posts = 0

        for post in posts:
            if post.attachments.exists():
                skipped_posts += 1
                continue

            file_ids = [p.strip() for p in post.files.split(',') if p.strip()]
            linked_this_post = 0
            for file_id in file_ids:
                entry = mapping.get(file_id)
                if not entry:
                    self.stderr.write(f'Post {post.id} (oldid={post.oldid}): FileID {file_id} not in mapping, skipping')
                    total_missing += 1
                    continue

                src_path = os.path.join(FILES_DIR, entry['FileSource'])
                if not os.path.isfile(src_path):
                    self.stderr.write(f'Post {post.id}: source file missing on disk: {src_path}')
                    total_missing += 1
                    continue

                if dry_run:
                    self.stdout.write(f'[dry-run] Post {post.id} <- FileID {file_id} ({entry["FileName"]})')
                    linked_this_post += 1
                    continue

                upload = FileUpload(
                    description=entry['FileName'],
                    uploader=uploader,
                )
                with open(src_path, 'rb') as fh:
                    upload.file.save(entry['FileSource'], File(fh), save=False)
                upload.save()
                post.attachments.add(upload)
                linked_this_post += 1

            if linked_this_post:
                total_posts += 1
                total_linked += linked_this_post

        self.stdout.write(self.style.SUCCESS(
            f'Posts processed: {total_posts}, files linked: {total_linked}, '
            f'missing: {total_missing}, posts already done (skipped): {skipped_posts}'
        ))
