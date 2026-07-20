from __future__ import annotations

import datetime as dt
import json
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

from plans.models import Box, BoxType, Chapter, Lesson, WeeklyReport, WeeklyReportDetail
from plans.weekly_plans import (
    _append_report_log,
    _midnight,
    _parse_clock,
    _parse_date_value,
    _report_covering,
    _student_or_response,
    check_weekly_report,
    get_weekly_report_details,
    normalize_day_name,
)


DAY_TO_PY_WEEKDAY = {
    "شنبه": 5,
    "یک‌شنبه": 6,
    "دوشنبه": 0,
    "سه‌شنبه": 1,
    "چهارشنبه": 2,
    "پنج‌شنبه": 3,
    "جمعه": 4,
}
PY_WEEKDAY_TO_DAY = {weekday: day for day, weekday in DAY_TO_PY_WEEKDAY.items()}
ALLOWED_BOX_TYPES = {"مطالعه", "ایونت", "تکلیف", "شناور"}


def date_for_day(week_start: dt.date, day_name: str) -> dt.date:
    """Return the matching calendar date inside the selected seven-day period.

    The Plan page permits any selected start date. Therefore day names must be
    resolved relative to that start date rather than assuming Saturday is
    always offset zero.
    """

    canonical_day = normalize_day_name(day_name)
    if canonical_day is None:
        raise ValueError(f"نام روز نامعتبر است: {day_name}")
    offset = (DAY_TO_PY_WEEKDAY[canonical_day] - week_start.weekday()) % 7
    return week_start + dt.timedelta(days=offset)


def _lesson_and_chapter(task: dict[str, Any]):
    lesson_id = task.get("lesson_id")
    chapter_id = task.get("chapter_id")
    if not lesson_id:
        raise ValueError("برای باکس مطالعه، انتخاب درس الزامی است.")

    lesson = Lesson.objects.select_related("grade", "lesson_type").get(pk=lesson_id)
    chapter = None
    if chapter_id:
        chapter = Chapter.objects.get(pk=chapter_id)
        if chapter.lesson_id != lesson.pk:
            raise ValueError("فصل انتخاب‌شده متعلق به این درس نیست.")
    return lesson, chapter


def _normalized_days(payload: dict[str, Any]):
    raw_days = payload.get("days")
    if not isinstance(raw_days, list):
        raise ValueError("ساختار روزهای برنامه نامعتبر است.")

    normalized: list[tuple[str, bool, list[dict[str, Any]]]] = []
    seen_days: set[str] = set()
    for raw_day in raw_days:
        if not isinstance(raw_day, dict):
            raise ValueError("ساختار یکی از روزها نامعتبر است.")
        day_name = normalize_day_name(raw_day.get("day"))
        if day_name is None:
            raise ValueError(f"نام روز نامعتبر است: {raw_day.get('day', '')}")
        if day_name in seen_days:
            raise ValueError(f"روز {day_name} بیش از یک بار ارسال شده است.")
        seen_days.add(day_name)

        tasks = raw_day.get("tasks") or []
        if not isinstance(tasks, list):
            raise ValueError(f"تسک‌های {day_name} نامعتبر است.")
        normalized.append((day_name, bool(raw_day.get("disabled")), tasks))
    return normalized


@login_required
@require_POST
def save_weekly_report(request: HttpRequest):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"status": "error", "message": "JSON نامعتبر است."}, status=400
        )

    student, error = _student_or_response(request, payload.get("student_id"))
    if error:
        return error

    week_start_date = _parse_date_value(payload.get("week_start"))
    week_end_date = _parse_date_value(payload.get("week_end"))
    if week_start_date is None or week_end_date is None:
        return JsonResponse(
            {
                "status": "error",
                "message": "تاریخ شروع یا پایان هفته نامعتبر است.",
            },
            status=400,
        )
    if week_end_date < week_start_date:
        return JsonResponse(
            {"status": "error", "message": "پایان هفته قبل از شروع هفته است."},
            status=400,
        )
    if (week_end_date - week_start_date).days != 6:
        return JsonResponse(
            {"status": "error", "message": "بازه برنامه باید دقیقاً هفت روز باشد."},
            status=400,
        )

    try:
        normalized_days = _normalized_days(payload)
    except ValueError as exc:
        return JsonResponse(
            {"status": "error", "message": str(exc)}, status=400
        )

    try:
        with transaction.atomic():
            report = (
                WeeklyReport.objects.select_for_update()
                .filter(student=student, week_start__date=week_start_date)
                .first()
            )
            created = report is None
            if report is None:
                report = WeeklyReport(
                    student=student,
                    week_start=_midnight(week_start_date),
                )

            report.week_end = _midnight(week_end_date) + dt.timedelta(
                hours=23, minutes=59, seconds=59
            )
            report.disabled_days = ",".join(
                day_name
                for day_name, disabled, _tasks in normalized_days
                if disabled
            )
            report.important_events = str(payload.get("important_events") or "")
            _append_report_log(
                report,
                "Report created" if created else "Report updated",
                {
                    "week_start": week_start_date.isoformat(),
                    "week_end": week_end_date.isoformat(),
                },
                request=request,
            )
            report.save()

            old_box_ids = list(report.details.values_list("box_id", flat=True))
            report.details.all().delete()
            if old_box_ids:
                Box.objects.filter(pk__in=old_box_ids, is_default=False).delete()

            box_types: dict[str, BoxType] = {}
            created_count = 0
            for day_name, is_disabled, tasks in normalized_days:
                box_date = date_for_day(week_start_date, day_name)
                if box_date > week_end_date:
                    raise ValueError(
                        f"روز {day_name} خارج از بازه انتخاب‌شده قرار گرفته است."
                    )

                for task in tasks:
                    if not isinstance(task, dict):
                        raise ValueError(
                            f"ساختار یک باکس در {day_name} نامعتبر است."
                        )

                    start_clock = _parse_clock(task.get("start"))
                    end_clock = _parse_clock(task.get("end"))
                    if start_clock is None or end_clock is None:
                        raise ValueError(
                            f"زمان یک باکس در {day_name} نامعتبر است."
                        )

                    start_datetime = _midnight(box_date).replace(
                        hour=start_clock.hour,
                        minute=start_clock.minute,
                        second=start_clock.second,
                    )
                    end_datetime = _midnight(box_date).replace(
                        hour=end_clock.hour,
                        minute=end_clock.minute,
                        second=end_clock.second,
                    )
                    if end_datetime <= start_datetime:
                        end_datetime += dt.timedelta(days=1)

                    duration_minutes = int(
                        (end_datetime - start_datetime).total_seconds() // 60
                    )
                    if duration_minutes <= 0 or duration_minutes > 24 * 60:
                        raise ValueError(
                            f"مدت یک باکس در {day_name} معتبر نیست."
                        )

                    box_type_name = str(
                        task.get("box_type") or "مطالعه"
                    ).strip()
                    if box_type_name not in ALLOWED_BOX_TYPES:
                        raise ValueError(
                            f"نوع باکس نامعتبر است: {box_type_name}"
                        )
                    box_type = box_types.get(box_type_name)
                    if box_type is None:
                        box_type, _ = BoxType.objects.get_or_create(
                            name=box_type_name
                        )
                        box_types[box_type_name] = box_type

                    lesson = None
                    chapter = None
                    if box_type_name == "مطالعه":
                        lesson, chapter = _lesson_and_chapter(task)

                    optional_tests_count = task.get(
                        "optional_tests_count"
                    ) or 0
                    try:
                        optional_tests_count = max(
                            int(optional_tests_count), 0
                        )
                    except (TypeError, ValueError):
                        optional_tests_count = 0

                    title = str(task.get("title") or "").strip()
                    if not title:
                        title = lesson.name if lesson else box_type_name

                    box = Box.objects.create(
                        box_type=box_type,
                        lesson=lesson,
                        chapter=chapter,
                        optional_tests_count=optional_tests_count,
                        duration_minutes=duration_minutes,
                        name=title,
                        is_default=False,
                    )
                    WeeklyReportDetail.objects.create(
                        report=report,
                        box=box,
                        start_time=start_datetime,
                        end_time=end_datetime,
                        day_of_week=day_name,
                        is_disabled=is_disabled,
                    )
                    created_count += 1

            _append_report_log(
                report,
                "Report details saved",
                {
                    "days_count": len(normalized_days),
                    "tasks_count": created_count,
                },
                request=request,
            )
            report.save(update_fields=["logs"])
    except (Lesson.DoesNotExist, Chapter.DoesNotExist):
        return JsonResponse(
            {
                "status": "error",
                "message": "درس یا فصل انتخاب‌شده پیدا نشد.",
            },
            status=400,
        )
    except (ValueError, BoxType.DoesNotExist) as exc:
        return JsonResponse(
            {"status": "error", "message": str(exc)}, status=400
        )

    return JsonResponse(
        {
            "status": "success",
            "report_id": report.pk,
            "tasks_count": created_count,
            "week_start": week_start_date.isoformat(),
            "week_end": week_end_date.isoformat(),
        }
    )


@login_required
@require_POST
def copy_day_plan(request: HttpRequest):
    source_student, source_error = _student_or_response(
        request, request.POST.get("source_student_id")
    )
    if source_error:
        return source_error
    target_student, target_error = _student_or_response(
        request, request.POST.get("target_student_id")
    )
    if target_error:
        return target_error

    source_date = _parse_date_value(request.POST.get("source_date"))
    target_day = normalize_day_name(request.POST.get("target_day_of_week"))
    if source_date is None or target_day is None:
        return JsonResponse(
            {
                "status": "error",
                "message": "تاریخ یا روز مقصد نامعتبر است.",
            },
            status=400,
        )

    source_report = _report_covering(source_student, source_date)
    if source_report is None:
        return JsonResponse(
            {
                "status": "error",
                "message": "برای روز مبدا برنامه‌ای پیدا نشد.",
            },
            status=404,
        )

    source_day = PY_WEEKDAY_TO_DAY[source_date.weekday()]
    source_day_aliases = {source_day, source_day.replace("\u200c", "")}
    source_details = list(
        source_report.details.filter(day_of_week__in=source_day_aliases)
        .select_related("box__box_type", "box__lesson", "box__chapter")
        .order_by("start_time", "pk")
    )
    if not source_details:
        return JsonResponse(
            {"status": "error", "message": "روز مبدا باکسی ندارد."},
            status=404,
        )

    target_week_start = source_report.week_start.date()
    target_week_end = source_report.week_end.date()
    target_date = date_for_day(target_week_start, target_day)
    if target_date > target_week_end:
        return JsonResponse(
            {
                "status": "error",
                "message": "روز مقصد خارج از بازه برنامه است.",
            },
            status=400,
        )

    target_day_aliases = {target_day, target_day.replace("\u200c", "")}
    with transaction.atomic():
        target_report = (
            WeeklyReport.objects.select_for_update()
            .filter(
                student=target_student,
                week_start__date=target_week_start,
            )
            .first()
        )
        if target_report is None:
            target_report = WeeklyReport.objects.create(
                student=target_student,
                week_start=source_report.week_start,
                week_end=source_report.week_end,
                disabled_days="",
                important_events="",
                logs=[],
            )

        old_box_ids = list(
            target_report.details.filter(
                day_of_week__in=target_day_aliases
            ).values_list("box_id", flat=True)
        )
        target_report.details.filter(
            day_of_week__in=target_day_aliases
        ).delete()
        if old_box_ids:
            Box.objects.filter(pk__in=old_box_ids, is_default=False).delete()

        for detail in source_details:
            source_box = detail.box
            copied_box = Box.objects.create(
                box_type=source_box.box_type,
                lesson=source_box.lesson,
                chapter=source_box.chapter,
                optional_tests_count=source_box.optional_tests_count,
                duration_minutes=source_box.duration_minutes,
                name=source_box.name,
                is_default=False,
            )
            duration = detail.end_time - detail.start_time
            start_time = detail.start_time.timetz().replace(tzinfo=None)
            copied_start = _midnight(target_date).replace(
                hour=start_time.hour,
                minute=start_time.minute,
                second=start_time.second,
            )
            WeeklyReportDetail.objects.create(
                report=target_report,
                box=copied_box,
                start_time=copied_start,
                end_time=copied_start + duration,
                day_of_week=target_day,
                is_disabled=False,
            )

        _append_report_log(
            target_report,
            "Copied day plan",
            {
                "source_student_id": source_student.pk,
                "source_date": source_date.isoformat(),
                "target_day": target_day,
            },
            request=request,
        )
        target_report.save(update_fields=["logs"])

    return JsonResponse(
        {
            "status": "success",
            "copied_details_count": len(source_details),
        }
    )
