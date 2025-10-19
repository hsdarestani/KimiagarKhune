from django.db import migrations, models


def ensure_index(schema_editor, table_name, index_name, columns):
    """Create the given index only when it is missing."""

    schema_editor.connection.ensure_connection()
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"SHOW INDEX FROM `{table_name}`")
        existing_indexes = {row[2] for row in cursor.fetchall()}

    if index_name in existing_indexes:
        return

    column_sql = ", ".join(f"`{column}`" for column in columns)
    schema_editor.execute(
        f"CREATE INDEX `{index_name}` ON `{table_name}` ({column_sql})"
    )


def create_loginotp_phone_index(apps, schema_editor):
    table_name = apps.get_model('accounts', 'LoginOTP')._meta.db_table
    ensure_index(
        schema_editor,
        table_name,
        'accounts_lo_phone_n_97a5e1_idx',
        ['phone_number'],
    )


def create_loginotp_expires_index(apps, schema_editor):
    table_name = apps.get_model('accounts', 'LoginOTP')._meta.db_table
    ensure_index(
        schema_editor,
        table_name,
        'accounts_lo_expires_3b86f9_idx',
        ['expires_at'],
    )


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0003_profile_telegram_chat_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoginOTP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_number', models.CharField(db_index=True, max_length=15)),
                ('code', models.CharField(max_length=6)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('attempt_count', models.PositiveSmallIntegerField(default=0)),
                ('is_used', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    create_loginotp_phone_index,
                    migrations.RunPython.noop,
                ),
                migrations.RunPython(
                    create_loginotp_expires_index,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name='loginotp',
                    index=models.Index(
                        fields=['phone_number'],
                        name='accounts_lo_phone_n_97a5e1_idx',
                    ),
                ),
                migrations.AddIndex(
                    model_name='loginotp',
                    index=models.Index(
                        fields=['expires_at'],
                        name='accounts_lo_expires_3b86f9_idx',
                    ),
                ),
            ],
        ),
    ]
