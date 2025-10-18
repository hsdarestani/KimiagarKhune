from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("plans", "0010_course_comment_session"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="class_link",
            field=models.URLField(blank=True, null=True, verbose_name="لینک کلاس"),
        ),
    ]
