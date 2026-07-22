from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from plans.models import WeeklyReport


DEMO_USERNAME_PREFIX = "demo_plan_student_"
DEFAULT_HORIZON_DAYS = 3650


class Command(BaseCommand):
    help = (
        "Delete implausibly far-future weekly reports belonging only to Plan demo "
        "students. This removes synthetic browser-test data without touching real students."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias to clean.",
        )
        parser.add_argument(
            "--horizon-days",
            type=int,
            default=DEFAULT_HORIZON_DAYS,
            help="Delete demo reports later than this many days from now.",
        )

    def handle(self, *args, **options):
        using = options["database"]
        horizon_days = max(365, int(options["horizon_days"]))
        cutoff = timezone.now() + timedelta(days=horizon_days)

        queryset = WeeklyReport.objects.using(using).filter(
            student__profile__user__username__startswith=DEMO_USERNAME_PREFIX,
            week_start__gt=cutoff,
        )
        report_count = queryset.count()
        deleted_objects, _details = queryset.delete()

        self.stdout.write(
            self.style.SUCCESS(
                "Plan demo report cleanup complete: "
                f"{report_count} weekly report(s) removed "
                f"({deleted_objects} total related object(s)); "
                f"cutoff={cutoff.date().isoformat()}."
            )
        )
