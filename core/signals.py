from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Profile


@receiver(post_save, sender=get_user_model())
def ensure_profile_exists(sender, instance, created, **kwargs):
    if not instance or not hasattr(instance, 'pk'):
        return
    try:
        Profile.objects.get_or_create(user=instance)
    except Exception:
        # Avoid blocking auth flows on errors
        pass

