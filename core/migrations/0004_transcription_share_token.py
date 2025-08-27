from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_transcription_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='transcription',
            name='share_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]

