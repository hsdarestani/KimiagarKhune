from django.db import connections
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .default_plan_data import seed_plan_defaults
from .lesson_import import import_lesson_graph
from .models import DefaultEvent


@receiver(post_migrate, dispatch_uid="plans.import_lesson_graph_1403")
def import_plan_reference_data_after_migrate(sender, using, verbosity, **kwargs):
    if sender.label != "plans":
        return

    lesson_summary = import_lesson_graph(using=using)

    default_summary = None
    connection = connections[using]
    if DefaultEvent._meta.db_table in connection.introspection.table_names():
        default_summary = seed_plan_defaults(using=using)

    if verbosity:
        message = (
            "Lesson graph ready: "
            f"{lesson_summary.rows} CSV rows, "
            f"{lesson_summary.lessons_created} lessons created, "
            f"{lesson_summary.chapters_created} chapters created."
        )
        if default_summary is not None:
            message += (
                " Plan defaults ready: "
                f"{default_summary.boxes_created} boxes, "
                f"{default_summary.students_created} students, "
                f"{default_summary.events_created} events created."
            )
        print(message)
