from django.db import migrations, models


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
        migrations.AddIndex(
            model_name='loginotp',
            index=models.Index(fields=['phone_number'], name='accounts_lo_phone_n_97a5e1_idx'),
        ),
        migrations.AddIndex(
            model_name='loginotp',
            index=models.Index(fields=['expires_at'], name='accounts_lo_expires_3b86f9_idx'),
        ),
    ]
