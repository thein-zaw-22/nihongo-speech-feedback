from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_merge_20250829_1612'),
    ]

    operations = [
        migrations.CreateModel(
            name='Puzzle',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100)),
                ('correct', models.TextField(help_text='Correct sentence')),
                ('tokens', models.JSONField(default=list, help_text='List of token strings in order')),
                ('furigana', models.JSONField(blank=True, default=list, help_text='Optional list of {base,ruby}')),
                ('gloss', models.TextField(blank=True, help_text='English gloss')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]

