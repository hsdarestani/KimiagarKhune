from __future__ import annotations

from django.core.management.base import BaseCommand

from accounts.models import Student
from plans.models import Course


class Command(BaseCommand):
    help = (
        "Repair Student.advisor for legacy dashboard assignments that created a "
        "Course but did not persist the student's advisor foreign key."
    )

    def handle(self, *args, **options):
        repaired = 0
        unchanged = 0
        without_active_course = 0

        students = Student.objects.select_related("profile", "advisor").order_by("pk")
        for student in students.iterator():
            advisor_id = (
                Course.objects.filter(student_id=student.pk, is_active=True)
                .order_by("-created_at", "-pk")
                .values_list("advisor_id", flat=True)
                .first()
            )
            if not advisor_id:
                without_active_course += 1
                continue

            if student.advisor_id == advisor_id:
                unchanged += 1
                continue

            old_id = student.advisor_id
            Student.objects.filter(pk=student.pk).update(advisor_id=advisor_id)
            repaired += 1
            name = student.profile.get_full_name() if student.profile_id else str(student.pk)
            self.stdout.write(
                f"Repaired student {student.pk} ({name}): advisor {old_id} -> {advisor_id}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Advisor assignment repair complete: "
                f"{repaired} repaired, {unchanged} already correct, "
                f"{without_active_course} without active course."
            )
        )
