from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_profile'),
    ]

    operations = [
        migrations.CreateModel(
            name='BatchJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(default='gemini', max_length=20)),
                ('input_file', models.FileField(upload_to='batch/')),
                ('output_file', models.FileField(blank=True, null=True, upload_to='batch_out/')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('done', 'Done'), ('error', 'Error')], default='pending', max_length=10)),
                ('total_rows', models.PositiveIntegerField(default=0)),
                ('processed_rows', models.PositiveIntegerField(default=0)),
                ('error_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batch_jobs', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]

