from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_batch_job'),
    ]

    operations = [
        migrations.AddField(
            model_name='batchjob',
            name='cancel_requested',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='batchjob',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('done', 'Done'), ('error', 'Error'), ('canceled', 'Canceled')], default='pending', max_length=10),
        ),
    ]

