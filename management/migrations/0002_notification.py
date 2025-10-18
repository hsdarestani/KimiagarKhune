from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('management', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField(verbose_name='متن اعلان')),
                ('send_via_panel', models.BooleanField(default=True, verbose_name='نمایش در پنل')),
                ('send_via_telegram', models.BooleanField(default=False, verbose_name='ارسال تلگرام')),
                ('send_via_sms', models.BooleanField(default=False, verbose_name='ارسال پیامک')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sender', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sent_notifications', to=settings.AUTH_USER_MODEL, verbose_name='فرستنده')),
            ],
        ),
        migrations.CreateModel(
            name='NotificationRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_read', models.BooleanField(default=False, verbose_name='خوانده شده')),
                ('telegram_sent', models.BooleanField(default=False, verbose_name='تلگرام ارسال شد')),
                ('sms_sent', models.BooleanField(default=False, verbose_name='پیامک ارسال شد')),
                ('telegram_error', models.TextField(blank=True, null=True, verbose_name='خطای تلگرام')),
                ('sms_error', models.TextField(blank=True, null=True, verbose_name='خطای پیامک')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('notification', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recipients', to='management.notification', verbose_name='اعلان')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='received_notifications', to=settings.AUTH_USER_MODEL, verbose_name='کاربر')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='notificationrecipient',
            unique_together={('notification', 'user')},
        ),
    ]
