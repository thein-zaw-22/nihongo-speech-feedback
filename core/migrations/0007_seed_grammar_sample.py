from django.db import migrations


def seed_data(apps, schema_editor):
    GrammarQuestion = apps.get_model('core', 'GrammarQuestion')
    GrammarChoice = apps.get_model('core', 'GrammarChoice')

    samples = [
        {
            'jlpt_level': 'N5', 'category': 'particle',
            'prompt': '学校__行きます。',
            'explanation': "Use へ or に for direction; に is more common for destination.",
            'choices': [
                {'text': 'に', 'is_correct': True},
                {'text': 'を', 'is_correct': False},
                {'text': 'が', 'is_correct': False},
            ],
        },
        {
            'jlpt_level': 'N5', 'category': 'particle',
            'prompt': '机__本を置きます。',
            'explanation': "Use の上に (on top of) or simply に for placing on a surface.",
            'choices': [
                {'text': 'に', 'is_correct': True},
                {'text': 'で', 'is_correct': False},
                {'text': 'を', 'is_correct': False},
            ],
        },
        {
            'jlpt_level': 'N4', 'category': 'verb_form',
            'prompt': '昨日映画を見__。',
            'explanation': 'Past tense polite form: 見ました。',
            'choices': [
                {'text': 'ました', 'is_correct': True},
                {'text': 'ます', 'is_correct': False},
                {'text': 'ません', 'is_correct': False},
            ],
        },
        {
            'jlpt_level': 'N3', 'category': 'politeness',
            'prompt': 'すみません、少々お待ち__。',
            'explanation': 'Polite request: ください。',
            'choices': [
                {'text': 'ください', 'is_correct': True},
                {'text': 'くださいません', 'is_correct': False},
                {'text': 'くれます', 'is_correct': False},
            ],
        },
        {
            'jlpt_level': 'N2', 'category': 'word_order',
            'prompt': '彼は日本語を上手に__。',
            'explanation': 'Adverb + verb: 話す (speaks well).',
            'choices': [
                {'text': '話す', 'is_correct': True},
                {'text': '話して', 'is_correct': False},
                {'text': '話しますか', 'is_correct': False},
            ],
        },
        {
            'jlpt_level': 'N1', 'category': 'vocab',
            'prompt': '彼の説明は__、理解しにくかった。',
            'explanation': '冗長 (じょうちょう, redundant) fits naturally here.',
            'choices': [
                {'text': '冗長で', 'is_correct': True},
                {'text': '簡潔で', 'is_correct': False},
                {'text': '鮮明で', 'is_correct': False},
            ],
        },
    ]

    for s in samples:
        q = GrammarQuestion.objects.create(
            jlpt_level=s['jlpt_level'], category=s['category'], prompt=s['prompt'], explanation=s['explanation'], is_active=True
        )
        for i, ch in enumerate(s['choices']):
            GrammarChoice.objects.create(question=q, text=ch['text'], is_correct=ch['is_correct'], order=i)


def unseed(apps, schema_editor):
    GrammarQuestion = apps.get_model('core', 'GrammarQuestion')
    prompts = [
        '学校__行きます。', '机__本を置きます。', '昨日映画を見__。', 'すみません、少々お待ち__。', '彼は日本語を上手に__。', '彼の説明は__、理解しにくかった。'
    ]
    GrammarQuestion.objects.filter(prompt__in=prompts).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_create_grammar_models'),
    ]

    operations = [
        migrations.RunPython(seed_data, reverse_code=unseed),
    ]

