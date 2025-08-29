from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

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


# ---------------- Grammar Game ----------------
class GrammarQuestion(models.Model):
    JLPT_LEVELS = [
        ("N5", "N5"), ("N4", "N4"), ("N3", "N3"), ("N2", "N2"), ("N1", "N1"),
    ]
    CATEGORY_CHOICES = [
        ("particle", "Particles"),
        ("verb_form", "Verb Forms"),
        ("politeness", "Politeness"),
        ("word_order", "Word Order"),
        ("vocab", "Vocabulary"),
    ]

    jlpt_level = models.CharField(max_length=2, choices=JLPT_LEVELS)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    prompt = models.TextField(help_text="Question text. Use __ to indicate a blank if needed.")
    explanation = models.TextField(blank=True, help_text="Short explanation shown after answering.")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.jlpt_level} {self.get_category_display()}] {self.prompt[:40]}"


class GrammarChoice(models.Model):
    question = models.ForeignKey(GrammarQuestion, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{'*' if self.is_correct else '-'} {self.text}"


class GrammarGameSession(models.Model):
    user = models.ForeignKey(get_user_model(), null=True, blank=True, on_delete=models.SET_NULL)
    jlpt_level = models.CharField(max_length=2, choices=GrammarQuestion.JLPT_LEVELS)
    category = models.CharField(max_length=20, choices=GrammarQuestion.CATEGORY_CHOICES)
    total_questions = models.PositiveIntegerField()
    correct = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(default=0)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} {self.jlpt_level}/{self.category} {self.correct}/{self.total_questions}"


class Profile(models.Model):
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile({self.user})"


class BatchJob(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('error', 'Error'),
        ('canceled', 'Canceled'),
    ]
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='batch_jobs')
    provider = models.CharField(max_length=20, default='gemini')
    input_file = models.FileField(upload_to='batch/')
    output_file = models.FileField(upload_to='batch_out/', blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    total_rows = models.PositiveIntegerField(default=0)
    processed_rows = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    cancel_requested = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def progress_percent(self):
        if self.total_rows:
            return int((self.processed_rows / max(1, self.total_rows)) * 100)
        return 0
