from __future__ import annotations

from django.db.models import Q, QuerySet

from accounts.models import Advisor, Student
from plans.models import Course


def latest_active_course_advisor_id(student_id: int) -> int | None:
    """Return the advisor from the most recently created active course."""

    return (
        Course.objects.filter(student_id=student_id, is_active=True)
        .order_by("-created_at", "-pk")
        .values_list("advisor_id", flat=True)
        .first()
    )


def effective_advisor_id(student: Student) -> int | None:
    """Resolve the student's current advisor.

    `Student.advisor` is the canonical relationship. Older dashboard versions only
    created a Course when assigning a student and left this FK empty. For those
    legacy records we temporarily fall back to the newest active course so access
    works immediately even before the repair command has run.
    """

    if student.advisor_id:
        return student.advisor_id
    return latest_active_course_advisor_id(student.pk)


def student_is_assigned_to_advisor(student: Student, advisor: Advisor) -> bool:
    return effective_advisor_id(student) == advisor.pk


def assigned_students_for_advisor(advisor: Advisor) -> QuerySet[Student]:
    """Students currently belonging to an advisor, including legacy assignments.

    A Course fallback is used only when the Student.advisor FK is null. This keeps
    a historical course from granting an old advisor access after a later explicit
    reassignment changed Student.advisor.
    """

    legacy_student_ids = Course.objects.filter(
        advisor=advisor,
        is_active=True,
        student__advisor__isnull=True,
    ).values_list("student_id", flat=True)

    return Student.objects.filter(
        Q(advisor=advisor)
        | Q(advisor__isnull=True, pk__in=legacy_student_ids)
    ).distinct()


def set_current_advisor(student: Student, advisor: Advisor) -> bool:
    """Persist the canonical student -> advisor relationship."""

    if student.advisor_id == advisor.pk:
        return False
    Student.objects.filter(pk=student.pk).update(advisor_id=advisor.pk)
    student.advisor_id = advisor.pk
    student.advisor = advisor
    return True
