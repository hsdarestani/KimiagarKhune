from django.db import migrations, models


def add_telegram_chat_id_column(apps, schema_editor):
    """Ensure the telegram_chat_id column exists without duplicating it."""

    Profile = apps.get_model('accounts', 'Profile')
    table_name = Profile._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            column.name for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

    if 'telegram_chat_id' in existing_columns:
        return

    field = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='شناسه تلگرام',
    )
    field.set_attributes_from_name('telegram_chat_id')
    schema_editor.add_field(Profile, field)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_profile_profile_picture'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_telegram_chat_id_column, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='profile',
                    name='telegram_chat_id',
                    field=models.CharField(
                        blank=True,
                        max_length=100,
                        null=True,
                        verbose_name='شناسه تلگرام',
                    ),
                ),
            ],
        ),
    ]
