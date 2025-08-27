from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transcription',
            name='audio_file',
            field=models.FileField(blank=True, null=True, upload_to='uploads/'),
        ),
    ]

