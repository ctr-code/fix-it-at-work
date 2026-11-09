from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile, Role


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    """Every new account gets a profile. Superusers are managers, everyone else starts as a reporter."""
    if created:
        Profile.objects.get_or_create(
            user=instance, defaults={'role': Role.MANAGER if instance.is_superuser else Role.REPORTER})
