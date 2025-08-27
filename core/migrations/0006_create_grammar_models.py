from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_add_user_fk_if_missing'),
    ]

    operations = [
        migrations.CreateModel(
            name='GrammarQuestion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jlpt_level', models.CharField(choices=[('N5', 'N5'), ('N4', 'N4'), ('N3', 'N3'), ('N2', 'N2'), ('N1', 'N1')], max_length=2)),
                ('category', models.CharField(choices=[('particle', 'Particles'), ('verb_form', 'Verb Forms'), ('politeness', 'Politeness'), ('word_order', 'Word Order'), ('vocab', 'Vocabulary')], max_length=20)),
                ('prompt', models.TextField(help_text='Question text. Use __ to indicate a blank if needed.')),
                ('explanation', models.TextField(blank=True, help_text='Short explanation shown after answering.')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='GrammarGameSession',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jlpt_level', models.CharField(choices=[('N5', 'N5'), ('N4', 'N4'), ('N3', 'N3'), ('N2', 'N2'), ('N1', 'N1')], max_length=2)),
                ('category', models.CharField(choices=[('particle', 'Particles'), ('verb_form', 'Verb Forms'), ('politeness', 'Politeness'), ('word_order', 'Word Order'), ('vocab', 'Vocabulary')], max_length=20)),
                ('total_questions', models.PositiveIntegerField()),
                ('correct', models.PositiveIntegerField(default=0)),
                ('duration_seconds', models.PositiveIntegerField(default=0)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='GrammarChoice',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=255)),
                ('is_correct', models.BooleanField(default=False)),
                ('order', models.PositiveIntegerField(default=0)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='choices', to='core.grammarquestion')),
            ],
            options={'ordering': ['order', 'id']},
        ),
        migrations.AddIndex(
            model_name='grammargamesession',
            index=models.Index(fields=['user', 'jlpt_level', 'category', 'created_at'], name='ggs_user_idx'),
        ),
    ]

