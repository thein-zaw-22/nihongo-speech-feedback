from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_transcription_share_token'),
    ]

    operations = [
        # Add user_id column if it's missing (PostgreSQL specific)
        migrations.RunSQL(
            sql=r"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='core_transcription' AND column_name='user_id'
                ) THEN
                    ALTER TABLE core_transcription ADD COLUMN user_id integer NULL;
                END IF;
            END$$;
            """,
            reverse_sql=r"""
            -- Keep the column on reverse; no-op to avoid data loss
            """,
        ),
        # Add FK constraint if missing
        migrations.RunSQL(
            sql=r"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'core_transcription_user_id_fkey'
                ) THEN
                    ALTER TABLE core_transcription
                    ADD CONSTRAINT core_transcription_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES auth_user(id)
                    ON DELETE SET NULL;
                END IF;
            END$$;
            """,
            reverse_sql=r"""
            ALTER TABLE core_transcription DROP CONSTRAINT IF EXISTS core_transcription_user_id_fkey;
            """,
        ),
        # Add index for user_id to speed up history queries
        migrations.RunSQL(
            sql=r"""
            CREATE INDEX IF NOT EXISTS core_transcription_user_id_idx
            ON core_transcription(user_id);
            """,
            reverse_sql=r"""
            DROP INDEX IF EXISTS core_transcription_user_id_idx;
            """,
        ),
    ]

