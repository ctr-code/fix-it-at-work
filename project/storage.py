"""Uploaded media in Cloudinary (used when CLOUDINARY_URL is set; see settings.STORAGES).

Uploads are stored as Cloudinary's "authenticated" type, so the plain Cloudinary address of a photo or voice
note doesn't work. People reach a file through the app (cases/files.py), which checks they may see the case
and then sends them to a signed link that expires after a few minutes.
"""
import os
import time

import cloudinary
import cloudinary.uploader
import cloudinary.utils
from cloudinary_storage.storage import MediaCloudinaryStorage

DELIVERY_TYPE = 'authenticated'
LINK_MINUTES = 5


class CloudinaryMediaStorage(MediaCloudinaryStorage):
    """Photos go up as images; voice notes (visits/audio/) as Cloudinary's 'video' type, which covers audio."""

    def _get_resource_type(self, name):
        return 'video' if 'visits/audio/' in name else 'image'

    def _upload(self, name, content):
        options = {'use_filename': True, 'resource_type': self._get_resource_type(name), 'tags': self.TAG,
                   'type': DELIVERY_TYPE}
        folder = os.path.dirname(name)
        if folder:
            options['folder'] = folder
        return cloudinary.uploader.upload(content, **options)

    def delete(self, name):
        response = cloudinary.uploader.destroy(name, invalidate=True, resource_type=self._get_resource_type(name),
                                               type=DELIVERY_TYPE)
        return response['result'] == 'ok'

    def _get_url(self, name):
        """A signed address, used by the storage itself (to check a file exists, or read it)."""
        name = self._prepend_prefix(name)
        return cloudinary.utils.cloudinary_url(name, resource_type=self._get_resource_type(name),
                                               type=DELIVERY_TYPE, sign_url=True, secure=True)[0]

    def url(self, name):
        """A signed link that stops working after LINK_MINUTES. Only handed out by the app's /files/ view,
        after it has checked the person may see the case."""
        return cloudinary.utils.private_download_url(
            self._prepend_prefix(name), None, resource_type=self._get_resource_type(name), type=DELIVERY_TYPE,
            expires_at=int(time.time()) + LINK_MINUTES * 60)
