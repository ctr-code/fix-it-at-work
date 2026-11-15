"""
Make photos and voice notes uploaded to Cloudinary before private links existed private too.

New uploads are stored as Cloudinary's "authenticated" type (project/storage.py). Older ones were "upload",
which anyone with the link can open. This moves each one to "authenticated", keeping its name, so the app's
signed links work for it and the old public link stops working. Run it once where Cloudinary is used:

    python manage.py make_uploads_private --dry-run   # list what would change
    python manage.py make_uploads_private

Files already private are skipped, so it is safe to run again.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from cases.files import all_file_names


class Command(BaseCommand):
    help = 'Move uploads made before private links to Cloudinary\'s authenticated (private) type.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='List the files without changing anything.')

    def handle(self, *args, dry_run=False, **options):
        backend = settings.STORAGES['default']['BACKEND']
        if not backend.endswith('CloudinaryMediaStorage'):
            raise CommandError('Uploads are not stored in Cloudinary here (CLOUDINARY_URL is not set), '
                               'so there is nothing to make private.')
        import cloudinary.exceptions
        import cloudinary.uploader
        from project.storage import DELIVERY_TYPE, CloudinaryMediaStorage
        storage = CloudinaryMediaStorage()
        moved = skipped = failed = 0
        for name in all_file_names():
            public_id = storage._prepend_prefix(name)
            resource_type = storage._get_resource_type(name)
            if dry_run:
                self.stdout.write(f'Would make private: {public_id} ({resource_type})')
                continue
            try:
                cloudinary.uploader.rename(public_id, public_id, type='upload', to_type=DELIVERY_TYPE,
                                           resource_type=resource_type, overwrite=False)
                moved += 1
            except cloudinary.exceptions.NotFound:
                skipped += 1  # not a public upload: already private, or gone
            except Exception as exc:  # noqa: BLE001 - report each failure and carry on with the rest
                failed += 1
                self.stderr.write(f'Could not change {public_id}: {exc}')
        if dry_run:
            return
        self.stdout.write(self.style.SUCCESS(
            f'Made private: {moved}. Already private or missing: {skipped}. Failed: {failed}.'))
