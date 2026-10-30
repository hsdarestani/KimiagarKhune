from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("plans", "0014_defaultevent"),
    ]

    operations = [
        migrations.AddField(
            model_name="box",
            name="study_mode",
            field=models.CharField(default="study", max_length=12),
        ),
        migrations.AddField(
            model_name="box",
            name="study_items",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
