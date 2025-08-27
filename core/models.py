from django.db import models
from django.contrib.auth import get_user_model

class Transcription(models.Model):
    user = models.ForeignKey(
        get_user_model(), null=True, blank=True,
        on_delete=models.SET_NULL, related_name='transcriptions'
    )
    # Make audio optional so text-only analyzes can be saved
    audio_file = models.FileField(upload_to="uploads/", blank=True, null=True)
    transcript = models.TextField()
    feedback = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
