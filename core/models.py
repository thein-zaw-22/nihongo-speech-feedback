from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

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


# ---------------- Puzzle (Japanese Syntax) ----------------
class Puzzle(models.Model):
    title = models.CharField(max_length=100)
    correct = models.TextField(help_text="Correct sentence")
    tokens = models.JSONField(help_text="List of token strings in order", default=list)
    furigana = models.JSONField(blank=True, default=list, help_text="Optional list of {base,ruby}")
    gloss = models.TextField(blank=True, help_text="English gloss")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)




# ---------------- Flashcards ----------------
class Flashcard(models.Model):
    JLPT_LEVELS = [
        ("N5", "N5"), ("N4", "N4"), ("N3", "N3"), ("N2", "N2"), ("N1", "N1"),
    ]
    CATEGORY_CHOICES = [
        ("vocabulary", "Vocabulary"),
        ("kanji", "Kanji"),
        ("grammar", "Grammar"),
        ("phrases", "Phrases"),
    ]

    jlpt_level = models.CharField(max_length=2, choices=JLPT_LEVELS)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    front = models.TextField(help_text="Front side (Japanese)")
    back = models.TextField(help_text="Back side (English/explanation)")
    reading = models.CharField(max_length=255, blank=True, help_text="Furigana/reading")
    example = models.TextField(blank=True, help_text="Example sentence")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.jlpt_level} {self.get_category_display()}] {self.front[:30]}"


class FlashcardSession(models.Model):
    user = models.ForeignKey(get_user_model(), null=True, blank=True, on_delete=models.SET_NULL)
    jlpt_level = models.CharField(max_length=2, choices=Flashcard.JLPT_LEVELS)
    category = models.CharField(max_length=20, choices=Flashcard.CATEGORY_CHOICES)
    total_cards = models.PositiveIntegerField()
    correct = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(default=0)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} {self.jlpt_level}/{self.category} {self.correct}/{self.total_cards}"


class FlashcardProgress(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    flashcard = models.ForeignKey(Flashcard, on_delete=models.CASCADE)
    ease_factor = models.FloatField(default=2.5)  # SM-2 algorithm ease factor
    interval = models.PositiveIntegerField(default=1)  # Days until next review
    repetitions = models.PositiveIntegerField(default=0)  # Number of successful repetitions
    next_review = models.DateTimeField(default=timezone.now)  # When to review next
    last_reviewed = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'flashcard')

    def update_progress(self, quality):
        """Update progress using SM-2 algorithm. Quality: 0-5 (0=total blackout, 5=perfect)"""
        from datetime import timedelta
        
        self.last_reviewed = timezone.now()
        
        if quality < 3:  # Failed
            self.repetitions = 0
            self.interval = 1
        else:  # Passed
            if self.repetitions == 0:
                self.interval = 1
            elif self.repetitions == 1:
                self.interval = 6
            else:
                self.interval = int(self.interval * self.ease_factor)
            
            self.repetitions += 1
        
        # Update ease factor
        self.ease_factor = max(1.3, self.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        
        # Set next review date
        self.next_review = timezone.now() + timedelta(days=self.interval)
        self.save()

    def __str__(self):
        return f"{self.user} - {self.flashcard.front} (next: {self.next_review.date()})"
