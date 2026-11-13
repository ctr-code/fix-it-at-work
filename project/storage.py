"""Uploaded media in Cloudinary (used when CLOUDINARY_URL is set; see settings.STORAGES)."""

from cloudinary_storage.storage import MediaCloudinaryStorage


class CloudinaryMediaStorage(MediaCloudinaryStorage):
    """Photos go up as images; voice notes (visits/audio/) as Cloudinary's 'video' type, which covers audio."""

    def _get_resource_type(self, name):
        return 'video' if 'visits/audio/' in name else 'image'
