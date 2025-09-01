from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from core.views import home, index, signup, feedback, history, flashcard, flashcard_play, flashcard_submit, flashcard_stats, pronunciation, grammar_game, grammar_play, grammar_submit, grammar_explain, grammar_history, profile, password_update, batch_correct, batch_create, batch_status, batch_download, batch_cancel, batch_history, batch_correction, puzzle, puzzle_data
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/home/', permanent=False)),
    path('home/', home, name='home'),
    path('speak-ai/', index, name='index'),
    # Batch correction endpoints (new URL scheme)
    path('batch-correction/create', batch_create, name='batch_create'),
    path('batch-correction/<int:pk>/status', batch_status, name='batch_status'),
    path('batch-correction/<int:pk>/download', batch_download, name='batch_download'),
    path('batch-correction/<int:pk>/cancel', batch_cancel, name='batch_cancel'),
    path('batch-correction/history', batch_history, name='batch_history'),
    path('batch-correction/', batch_correction, name='batch_correction'),
    path('batch-correction/direct', batch_correct, name='batch_correct'),
    path('feedback/<int:pk>/', feedback, name='feedback'),
    path('history/', history, name='history'),
    path('flashcard/', flashcard, name='flashcard'),
    path('flashcard/play', flashcard_play, name='flashcard_play'),
    path('flashcard/submit', flashcard_submit, name='flashcard_submit'),
    path('flashcard/stats', flashcard_stats, name='flashcard_stats'),
    path('pronunciation/', pronunciation, name='pronunciation'),
    path('grammar-game/', grammar_game, name='grammar_game'),
    path('grammar-game/play', grammar_play, name='grammar_play'),
    path('grammar-game/submit', grammar_submit, name='grammar_submit'),
    path('grammar-game/explain', grammar_explain, name='grammar_explain'),
    path('grammar-game/history', grammar_history, name='grammar_history'),
    path('puzzle/', puzzle, name='puzzle'),
    path('puzzle/data', puzzle_data, name='puzzle_data'),
    # Profile
    path('profile/', profile, name='profile'),
    # Auth
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/signup/', signup, name='signup'),
    path('accounts/password/', password_update, name='password_update'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
