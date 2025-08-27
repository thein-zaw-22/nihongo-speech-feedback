from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_alter_transcription_audio_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='transcription',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transcriptions', to=settings.AUTH_USER_MODEL),
        ),
    ]

