from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from core.views import home, index, signup, feedback, history, flashcard, pronunciation, grammar_game
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/home/', permanent=False)),
    path('home/', home, name='home'),
    path('speak-ai/', index, name='index'),
    path('feedback/<int:pk>/', feedback, name='feedback'),
    path('history/', history, name='history'),
    path('flashcard/', flashcard, name='flashcard'),
    path('pronunciation/', pronunciation, name='pronunciation'),
    path('grammar-game/', grammar_game, name='grammar_game'),
    # Auth
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/signup/', signup, name='signup'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
