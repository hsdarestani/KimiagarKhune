from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from plans.default_plan_data import ensure_advisor_for_user, seed_plan_defaults


class Command(BaseCommand):
    help = "Seed default plan box types, palette boxes, demo students and events."

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias to seed.",
        )
        parser.add_argument(
            "--advisor-username",
            default="",
            help="Assign demo students to this existing Django user as advisor.",
        )

    def handle(self, *args, **options):
        using = options["database"]
        advisor = None
        advisor_username = (options.get("advisor_username") or "").strip()

        if advisor_username:
            User = get_user_model()
            try:
                user = User.objects.using(using).get(username=advisor_username)
            except User.DoesNotExist as exc:
                raise CommandError(
                    f"User '{advisor_username}' was not found."
                ) from exc
            advisor = ensure_advisor_for_user(user, using=using)

        summary = seed_plan_defaults(using=using, advisor=advisor)
        self.stdout.write(
            self.style.SUCCESS(
                "Plan defaults ready: "
                f"box types +{summary.box_types_created}; "
                f"boxes +{summary.boxes_created}/~{summary.boxes_updated}; "
                f"students +{summary.students_created}/~{summary.students_updated}; "
                f"events +{summary.events_created}."
            )
        )
