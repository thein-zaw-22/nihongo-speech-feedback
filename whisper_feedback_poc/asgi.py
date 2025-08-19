import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'whisper_feedback_poc.settings')
application = get_asgi_application()
