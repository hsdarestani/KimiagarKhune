from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_profile_profile_picture'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='telegram_chat_id',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='شناسه تلگرام'),
        ),
    ]
