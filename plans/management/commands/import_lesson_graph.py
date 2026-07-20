from django.core.management.base import BaseCommand, CommandError

from plans.lesson_import import DEFAULT_LESSON_GRAPH_PATH, import_lesson_graph


class Command(BaseCommand):
    help = "Import the 1403 lesson/chapter graph from CSV (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(DEFAULT_LESSON_GRAPH_PATH),
            help="Path to a UTF-8 CSV file with the lesson graph.",
        )
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias to import into.",
        )

    def handle(self, *args, **options):
        try:
            summary = import_lesson_graph(
                options["path"],
                using=options["database"],
            )
        except (FileNotFoundError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Import completed: "
                f"{summary.rows} rows; "
                f"lessons +{summary.lessons_created}/~{summary.lessons_updated}; "
                f"chapters +{summary.chapters_created}/~{summary.chapters_updated}; "
                f"grades +{summary.grades_created}; "
                f"majors +{summary.majors_created}; "
                f"lesson types +{summary.lesson_types_created}."
            )
        )
