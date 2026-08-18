from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse

from plans.models import WeeklyReport, WeeklyReportDetail
from plans.weekly_plans import _student_or_response, normalize_day_name


@login_required
def get_last_weekly_report(request: HttpRequest):
    """Return the latest reusable study plan, not merely the latest report row.

    A newer report may legitimately contain only events/classes (or no details).
    The old endpoint selected that row first and then filtered it down to study
    boxes, which made the UI say that no saved plan existed even when an older
    report contained a complete lesson plan.
    """

    student, error = _student_or_response(request, request.GET.get("student_id"))
    if error:
        return error

    report = (
        WeeklyReport.objects.filter(
            student=student,
            details__box__lesson__isnull=False,
        )
        .distinct()
        .order_by("-week_start", "-pk")
        .first()
    )
    if report is None:
        return JsonResponse({"report_id": None, "tasks": []})

    details = (
        WeeklyReportDetail.objects.filter(
            report=report,
            box__lesson__isnull=False,
        )
        .select_related(
            "box__lesson__grade",
            "box__lesson__lesson_type",
            "box__chapter",
        )
        .order_by("start_time", "pk")
    )

    tasks = []
    for detail in details:
        box = detail.box
        lesson = box.lesson
        if lesson is None:
            continue
        chapter = box.chapter
        duration_minutes = box.duration_minutes
        if not duration_minutes:
            duration_minutes = max(
                1,
                int((detail.end_time - detail.start_time).total_seconds() // 60),
            )
        day_name = normalize_day_name(detail.day_of_week)
        if day_name is None:
            # Historic rows occasionally used an alias. Falling back to the
            # actual calendar date is safer than silently mapping to Saturday.
            weekday_map = {
                5: "شنبه",
                6: "یک‌شنبه",
                0: "دوشنبه",
                1: "سه‌شنبه",
                2: "چهارشنبه",
                3: "پنج‌شنبه",
                4: "جمعه",
            }
            day_name = weekday_map[detail.start_time.weekday()]

        tasks.append(
            {
                "lesson_id": lesson.pk,
                "lesson_name": lesson.name,
                "chapter_id": chapter.pk if chapter else None,
                "chapter_text": chapter.name if chapter else "",
                "optional_tests_count": box.optional_tests_count or 0,
                "duration_minutes": duration_minutes,
                "grade_id": lesson.grade_id,
                "lesson_type": lesson.lesson_type.name if lesson.lesson_type else "",
                "grade": lesson.grade_id,
                "day_of_week": day_name,
            }
        )

    return JsonResponse(
        {
            "report_id": report.pk,
            "week_start": report.week_start.isoformat(),
            "week_end": report.week_end.isoformat(),
            "tasks": tasks,
        }
    )
