from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.html import format_html
import csv, io, json

from .models import GrammarQuestion, GrammarChoice, GrammarGameSession, Transcription, Profile, BatchJob, Puzzle


class ChoiceInline(admin.TabularInline):
    model = GrammarChoice
    extra = 2


@admin.register(GrammarQuestion)
class GrammarQuestionAdmin(admin.ModelAdmin):
    list_display = ("prompt", "jlpt_level", "category", "is_active", "created_at")
    list_filter = ("jlpt_level", "category", "is_active")
    search_fields = ("prompt", "explanation")
    inlines = [ChoiceInline]

    change_list_template = "admin/grammar_question_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("import/", self.admin_site.admin_view(self.import_view), name="grammar_import"),
        ]
        return custom + urls

    def import_view(self, request):
        if request.method == 'POST' and request.FILES.get('file'):
            f = request.FILES['file']
            name = f.name.lower()
            created = 0
            try:
                if name.endswith('.csv'):
                    data = io.StringIO(f.read().decode('utf-8'))
                    reader = csv.DictReader(data)
                    for row in reader:
                        q = GrammarQuestion.objects.create(
                            jlpt_level=row.get('jlpt_level', 'N5'),
                            category=row.get('category', 'particle'),
                            prompt=row.get('prompt', ''),
                            explanation=row.get('explanation', ''),
                            is_active=str(row.get('is_active', '1')).strip() not in ('0','false','False')
                        )
                        choices = row.get('choices', '')
                        correct = row.get('correct')
                        # choices pipe or JSON array
                        items = []
                        if choices:
                            if choices.strip().startswith('['):
                                items = json.loads(choices)
                            else:
                                items = [c.strip() for c in choices.split('|') if c.strip()]
                        for i, ch in enumerate(items):
                            text = ch['text'] if isinstance(ch, dict) else ch
                            is_ok = False
                            if isinstance(ch, dict):
                                is_ok = bool(ch.get('is_correct'))
                            elif correct is not None:
                                try:
                                    is_ok = (int(correct) == i)
                                except Exception:
                                    is_ok = (text == correct)
                            GrammarChoice.objects.create(question=q, text=text, is_correct=is_ok, order=i)
                        created += 1
                    messages.success(request, f"Imported {created} questions from CSV.")
                elif name.endswith('.json'):
                    payload = json.loads(f.read().decode('utf-8'))
                    for row in payload:
                        q = GrammarQuestion.objects.create(
                            jlpt_level=row.get('jlpt_level', 'N5'),
                            category=row.get('category', 'particle'),
                            prompt=row.get('prompt', ''),
                            explanation=row.get('explanation', ''),
                            is_active=bool(row.get('is_active', True))
                        )
                        for i, ch in enumerate(row.get('choices', [])):
                            GrammarChoice.objects.create(
                                question=q,
                                text=ch.get('text', ''),
                                is_correct=bool(ch.get('is_correct', False)),
                                order=i,
                            )
                        created += 1
                    messages.success(request, f"Imported {created} questions from JSON.")
                else:
                    messages.error(request, "Unsupported file type. Use CSV or JSON.")
            except Exception as e:
                messages.error(request, f"Import failed: {e}")
            return redirect('..')
        return render(request, 'admin/grammar_import.html')


@admin.register(GrammarGameSession)
class GrammarGameSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "jlpt_level", "category", "correct", "total_questions", "duration_seconds", "created_at")
    list_filter = ("jlpt_level", "category", "created_at")
    search_fields = ("user__username",)


@admin.register(Transcription)
class TranscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
    readonly_fields = ("feedback",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "updated_at")


@admin.register(BatchJob)
class BatchJobAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "provider", "status", "processed_rows", "total_rows", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("user__username",)


@admin.register(Puzzle)
class PuzzleAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("title", "correct", "gloss")
    change_list_template = "admin/puzzle_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("import/", self.admin_site.admin_view(self.import_view), name="puzzle_import"),
        ]
        return custom + urls

    def import_view(self, request):
        if request.method == 'POST' and request.FILES.get('file'):
            f = request.FILES['file']
            name = f.name.lower()
            created = 0
            try:
                if name.endswith('.csv'):
                    data = io.StringIO(f.read().decode('utf-8'))
                    reader = csv.DictReader(data)
                    for row in reader:
                        tokens = row.get('tokens', '')
                        toks = []
                        if tokens:
                            toks = json.loads(tokens) if tokens.strip().startswith('[') else [t.strip() for t in tokens.split('|') if t.strip()]
                        furigana = row.get('furigana', '').strip()
                        furi = json.loads(furigana) if (furigana.startswith('[') or furigana.startswith('{')) else []
                        Puzzle.objects.create(
                            title=row.get('title', ''),
                            correct=row.get('correct', ''),
                            tokens=toks,
                            furigana=furi,
                            gloss=row.get('gloss', ''),
                            is_active=str(row.get('is_active', '1')).strip() not in ('0','false','False')
                        )
                        created += 1
                    messages.success(request, f"Imported {created} puzzles from CSV.")
                elif name.endswith('.json'):
                    payload = json.loads(f.read().decode('utf-8'))
                    for row in payload:
                        Puzzle.objects.create(
                            title=row.get('title', ''),
                            correct=row.get('correct', ''),
                            tokens=row.get('tokens', []) or [],
                            furigana=row.get('furigana', []) or [],
                            gloss=row.get('gloss', ''),
                            is_active=bool(row.get('is_active', True))
                        )
                        created += 1
                    messages.success(request, f"Imported {created} puzzles from JSON.")
                else:
                    messages.error(request, "Unsupported file type. Use CSV or JSON.")
            except Exception as e:
                messages.error(request, f"Import failed: {e}")
            return redirect('..')
        return render(request, 'admin/puzzle_import.html')
