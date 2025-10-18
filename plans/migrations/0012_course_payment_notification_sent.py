from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("plans", "0011_course_class_link"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="payment_notification_sent",
            field=models.BooleanField(
                default=False,
                verbose_name="اطلاع‌رسانی پرداخت ارسال شده؟",
            ),
        ),
    ]
