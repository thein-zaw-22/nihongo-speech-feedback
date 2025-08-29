def inject_user_profile(request):
    profile = None
    avatar_url = None
    try:
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            # Import locally to avoid early model import
            from .models import Profile
            profile, _ = Profile.objects.get_or_create(user=user)
            if profile.avatar:
                try:
                    avatar_url = profile.avatar.url
                except Exception:
                    avatar_url = None
    except Exception:
        profile = None
        avatar_url = None
    return {
        'user_profile': profile,
        'user_avatar_url': avatar_url,
    }

