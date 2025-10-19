from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plans', '0012_course_payment_notification_sent'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='plan_file',
            field=models.FileField(blank=True, null=True, upload_to='session_plans/', verbose_name='برنامه هفتگی جلسه'),
        ),
        migrations.AddField(
            model_name='session',
            name='plan_uploaded_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='تاریخ بارگذاری برنامه'),
        ),
        migrations.AddField(
            model_name='session',
            name='plan_uploaded_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='uploaded_session_plans', to=settings.AUTH_USER_MODEL, verbose_name='بارگذاری توسط'),
        ),
    ]
