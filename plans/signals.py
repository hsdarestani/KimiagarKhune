from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .lesson_import import import_lesson_graph


@receiver(post_migrate, dispatch_uid="plans.import_lesson_graph_1403")
def import_lesson_graph_after_migrate(sender, using, verbosity, **kwargs):
    if sender.label != "plans":
        return

    summary = import_lesson_graph(using=using)
    if verbosity:
        print(
            "Lesson graph ready: "
            f"{summary.rows} CSV rows, "
            f"{summary.lessons_created} lessons created, "
            f"{summary.chapters_created} chapters created."
        )
