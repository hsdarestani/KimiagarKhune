from django.db import migrations


def repair_advisor_profile_roles(apps, schema_editor):
    Advisor = apps.get_model("accounts", "Advisor")
    Profile = apps.get_model("accounts", "Profile")

    advisor_profile_ids = Advisor.objects.values_list("profile_id", flat=True)
    Profile.objects.filter(
        pk__in=advisor_profile_ids,
        role="student",
    ).update(role="advisor")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_advisoravailability"),
    ]

    operations = [
        migrations.RunPython(repair_advisor_profile_roles, migrations.RunPython.noop),
    ]
