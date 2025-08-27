from django.db import models

class Transcription(models.Model):
    # Make audio optional so text-only analyzes can be saved
    audio_file = models.FileField(upload_to="uploads/", blank=True, null=True)
    transcript = models.TextField()
    feedback = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
