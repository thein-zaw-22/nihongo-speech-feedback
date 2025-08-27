from django.db import migrations


def noop_forward(apps, schema_editor):
    # Deprecated migration: share_token field was removed from the model.
    # Intentionally do nothing to avoid unique index errors on legacy data.
    return


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_transcription_user'),
    ]

    operations = [
        migrations.RunPython(noop_forward, reverse_code=noop_reverse),
    ]
