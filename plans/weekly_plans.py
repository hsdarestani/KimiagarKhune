from __future__ import annotations

import datetime as dt
import json
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime, parse_time
from django.views.decorators.http import require_GET, require_POST

from accounts.models import Advisor, Profile, Student
from plans.models import Box, BoxType, Chapter, Lesson, WeeklyReport, WeeklyReportDetail


CANONICAL_DAYS = (
    "شنبه",
    "یک‌شنبه",
    "دوشنبه",
    "سه‌شنبه",
    "چهارشنبه",
    "پنج‌شنبه",
    "جمعه",
)
DAY_OFFSETS = {name: index for index, name in enumerate(CANONICAL_DAYS)}


def _day_key(value: object) -> str:
    return (
        str(value or "")
        .strip()
        .replace("\u200c", "")
        .replace("\u200e", "")
        .replace("\u200f", "")
        .replace(" ", "")
        .replace("ي", "ی")
        .replace("ى", "ی")
        .replace("ك", "ک")
    )


DAY_ALIASES = {_day_key(day): day for day in CANONICAL_DAYS}


def normalize_day_name(value: object) -> str | None:
    return DAY_ALIASES.get(_day_key(value))


def _request_profile(request: HttpRequest) -> Profile | None:
    try:
        return request.user.profile
    except (AttributeError, Profile.DoesNotExist):
        return None


def _can_access_student(request: HttpRequest, student: Student) -> bool:
    if request.user.is_staff:
        return True

    profile = _request_profile(request)
    if profile is None:
        return False
    if profile.role == "student":
        return student.profile_id == profile.pk
    if profile.role == "advisor":
        return Advisor.objects.filter(profile=profile, student=student).exists()
    return False


def _student_or_response(request: HttpRequest, student_id: object):
    if not student_id:
        return None, JsonResponse({"status": "error", "message": "دانش‌آموز انتخاب نشده است."}, status=400)
    try:
        student = Student.objects.select_related("profile", "advisor__profile").get(pk=student_id)
    except (Student.DoesNotExist, TypeError, ValueError):
        return None, JsonResponse({"status": "error", "message": "دانش‌آموز پیدا نشد."}, status=404)
    if not _can_access_student(request, student):
        return None, JsonResponse({"status": "error", "message": "دسترسی به این دانش‌آموز مجاز نیست."}, status=403)
    return student, None


def _parse_date_value(value: object) -> dt.date | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    parsed_date = parse_date(raw)
    if parsed_date is not None:
        return parsed_date

    parsed_datetime = parse_datetime(raw)
    if parsed_datetime is None:
        return None
    if timezone.is_aware(parsed_datetime):
        parsed_datetime = timezone.localtime(parsed_datetime)
    return parsed_datetime.date()


def _midnight(value: dt.date) -> dt.datetime:
    naive = dt.datetime.combine(value, dt.time.min)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def _parse_clock(value: object) -> dt.time | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = parse_time(raw)
    if parsed is not None:
        return parsed.replace(tzinfo=None)
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return dt.datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    return None


def _report_covering(student: Student, selected_date: dt.date) -> WeeklyReport | None:
    return (
        WeeklyReport.objects.filter(
            student=student,
            week_start__date__lte=selected_date,
            week_end__date__gte=selected_date,
        )
        .order_by("-week_start")
        .first()
    )


def _append_report_log(
    report: WeeklyReport,
    action: str,
    data: dict[str, Any] | None,
    *,
    request: HttpRequest,
) -> None:
    logs = list(report.logs or [])
    logs.append(
        {
            "timestamp": timezone.now().isoformat(),
            "action": action,
            "user": {
                "id": request.user.pk,
                "username": request.user.get_username(),
            },
            "data": data or {},
        }
    )
    report.logs = logs


def _serialize_detail(detail: WeeklyReportDetail) -> dict[str, Any]:
    box = detail.box
    lesson = box.lesson
    chapter = box.chapter
    return {
        "id": detail.pk,
        "box_type": box.box_type.name,
        "title": box.name or (lesson.name if lesson else ""),
        "lesson_id": lesson.pk if lesson else None,
        "lesson_name": lesson.name if lesson else None,
        "lesson_type": lesson.lesson_type.name if lesson and lesson.lesson_type_id else "",
        "grade": lesson.grade_id if lesson else None,
        "chapter_id": chapter.pk if chapter else None,
        "chapter_text": (
            f"{chapter.chapter_number} - {chapter.name}" if chapter else ""
        ),
        "optional_tests_count": box.optional_tests_count or 0,
        "extra": box.optional_tests_count or 0,
        "duration_minutes": box.duration_minutes or int(
            (detail.end_time - detail.start_time).total_seconds() // 60
        ),
        "start_time": detail.start_time.isoformat(),
        "end_time": detail.end_time.isoformat(),
        "date": timezone.localtime(detail.start_time).date().isoformat()
        if timezone.is_aware(detail.start_time)
        else detail.start_time.date().isoformat(),
        "day_of_week": normalize_day_name(detail.day_of_week) or detail.day_of_week,
        "is_disabled": detail.is_disabled,
    }


@login_required
@require_GET
def check_weekly_report(request: HttpRequest):
    selected_date = _parse_date_value(request.GET.get("selected_date"))
    if selected_date is None:
        return HttpResponseBadRequest("Invalid selected_date.")

    student, error = _student_or_response(request, request.GET.get("student_id"))
    if error:
        return error

    report = _report_covering(student, selected_date)
    if report is not None:
        return JsonResponse(
            {
                "exists": "current",
                "report_id": report.pk,
                "week_start": report.week_start.date().isoformat(),
                "week_end": report.week_end.date().isoformat(),
            }
        )

    future = (
        WeeklyReport.objects.filter(student=student, week_start__date__gt=selected_date)
        .order_by("week_start")
        .first()
    )
    if future is not None:
        return JsonResponse(
            {
                "exists": "future",
                "report_id": future.pk,
                "week_start": future.week_start.date().isoformat(),
                "week_end": future.week_end.date().isoformat(),
            }
        )
    return JsonResponse({"exists": False})


@login_required
@require_GET
def get_weekly_report_details(request: HttpRequest):
    selected_date = _parse_date_value(request.GET.get("week_start"))
    if selected_date is None:
        return HttpResponseBadRequest("Invalid week_start.")

    student, error = _student_or_response(request, request.GET.get("student_id"))
    if error:
        return error

    report = (
        WeeklyReport.objects.filter(student=student, week_start__date=selected_date)
        .order_by("-week_start")
        .first()
    ) or _report_covering(student, selected_date)

    if report is None:
        return JsonResponse(
            {
                "report_id": None,
                "week_start": selected_date.isoformat(),
                "week_end": (selected_date + dt.timedelta(days=6)).isoformat(),
                "important_events": "",
                "disabled_days": [],
                "tasks": [],
            }
        )

    details = (
        WeeklyReportDetail.objects.filter(report=report)
        .select_related(
            "box__box_type",
            "box__lesson__lesson_type",
            "box__lesson__grade",
            "box__chapter",
        )
        .order_by("start_time", "pk")
    )
    disabled_days = [
        normalize_day_name(day) or day
        for day in (report.disabled_days or "").split(",")
        if day.strip()
    ]
    _append_report_log(
        report,
        "Load Weekly Report",
        {"selected_date": selected_date.isoformat()},
        request=request,
    )
    report.save(update_fields=["logs"])

    return JsonResponse(
        {
            "report_id": report.pk,
            "week_start": report.week_start.date().isoformat(),
            "week_end": report.week_end.date().isoformat(),
            "important_events": report.important_events or "",
            "disabled_days": disabled_days,
            "tasks": [_serialize_detail(detail) for detail in details],
        }
    )


def _lesson_and_chapter(task: dict[str, Any]):
    lesson_id = task.get("lesson_id")
    chapter_id = task.get("chapter_id")
    lesson = None
    chapter = None

    if lesson_id:
        lesson = Lesson.objects.select_related("grade", "lesson_type").get(pk=lesson_id)
    if chapter_id:
        chapter = Chapter.objects.get(pk=chapter_id)
        if lesson is None or chapter.lesson_id != lesson.pk:
            raise ValueError("فصل انتخاب‌شده متعلق به این درس نیست.")
    return lesson, chapter


@login_required
@require_POST
def save_weekly_report(request: HttpRequest):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON نامعتبر است."}, status=400)

    student, error = _student_or_response(request, payload.get("student_id"))
    if error:
        return error

    week_start_date = _parse_date_value(payload.get("week_start"))
    week_end_date = _parse_date_value(payload.get("week_end"))
    if week_start_date is None or week_end_date is None:
        return JsonResponse({"status": "error", "message": "تاریخ شروع یا پایان هفته نامعتبر است."}, status=400)
    if week_end_date < week_start_date:
        return JsonResponse({"status": "error", "message": "پایان هفته قبل از شروع هفته است."}, status=400)
    if (week_end_date - week_start_date).days > 7:
        return JsonResponse({"status": "error", "message": "بازه برنامه بیشتر از یک هفته است."}, status=400)

    raw_days = payload.get("days")
    if not isinstance(raw_days, list):
        return JsonResponse({"status": "error", "message": "ساختار روزهای برنامه نامعتبر است."}, status=400)

    normalized_days: list[tuple[str, bool, list[dict[str, Any]]]] = []
    for raw_day in raw_days:
        if not isinstance(raw_day, dict):
            return JsonResponse({"status": "error", "message": "ساختار یکی از روزها نامعتبر است."}, status=400)
        day_name = normalize_day_name(raw_day.get("day"))
        if day_name is None:
            return JsonResponse({"status": "error", "message": f"نام روز نامعتبر است: {raw_day.get('day', '')}"}, status=400)
        tasks = raw_day.get("tasks") or []
        if not isinstance(tasks, list):
            return JsonResponse({"status": "error", "message": f"تسک‌های {day_name} نامعتبر است."}, status=400)
        normalized_days.append((day_name, bool(raw_day.get("disabled")), tasks))

    try:
        with transaction.atomic():
            report = (
                WeeklyReport.objects.select_for_update()
                .filter(student=student, week_start__date=week_start_date)
                .first()
            )
            created = report is None
            if report is None:
                report = WeeklyReport(student=student, week_start=_midnight(week_start_date))

            report.week_end = _midnight(week_end_date) + dt.timedelta(hours=23, minutes=59, seconds=59)
            report.disabled_days = ",".join(
                day_name for day_name, disabled, _tasks in normalized_days if disabled
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
                box_date = week_start_date + dt.timedelta(days=DAY_OFFSETS[day_name])
                for task in tasks:
                    if not isinstance(task, dict):
                        raise ValueError(f"ساختار یک باکس در {day_name} نامعتبر است.")

                    start_clock = _parse_clock(task.get("start"))
                    end_clock = _parse_clock(task.get("end"))
                    if start_clock is None or end_clock is None:
                        raise ValueError(f"زمان یک باکس در {day_name} نامعتبر است.")

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
                        raise ValueError(f"مدت یک باکس در {day_name} معتبر نیست.")

                    box_type_name = str(task.get("box_type") or "مطالعه").strip()
                    if box_type_name not in {"مطالعه", "ایونت", "تکلیف", "شناور"}:
                        raise ValueError(f"نوع باکس نامعتبر است: {box_type_name}")
                    box_type = box_types.get(box_type_name)
                    if box_type is None:
                        box_type, _ = BoxType.objects.get_or_create(name=box_type_name)
                        box_types[box_type_name] = box_type

                    lesson = None
                    chapter = None
                    if box_type_name == "مطالعه":
                        lesson, chapter = _lesson_and_chapter(task)

                    optional_tests_count = task.get("optional_tests_count") or 0
                    try:
                        optional_tests_count = max(int(optional_tests_count), 0)
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
                {"days_count": len(normalized_days), "tasks_count": created_count},
                request=request,
            )
            report.save(update_fields=["logs"])
    except (Lesson.DoesNotExist, Chapter.DoesNotExist):
        return JsonResponse({"status": "error", "message": "درس یا فصل انتخاب‌شده پیدا نشد."}, status=400)
    except (ValueError, BoxType.DoesNotExist) as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=400)

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
        return JsonResponse({"status": "error", "message": "تاریخ یا روز مقصد نامعتبر است."}, status=400)

    source_report = _report_covering(source_student, source_date)
    if source_report is None:
        return JsonResponse({"status": "error", "message": "برای روز مبدا برنامه‌ای پیدا نشد."}, status=404)

    source_day = CANONICAL_DAYS[(source_date - source_report.week_start.date()).days % 7]
    source_details = list(
        source_report.details.filter(day_of_week__in={source_day, source_day.replace("\u200c", "")})
        .select_related("box__box_type", "box__lesson", "box__chapter")
        .order_by("start_time", "pk")
    )
    if not source_details:
        return JsonResponse({"status": "error", "message": "روز مبدا باکسی ندارد."}, status=404)

    target_week_start = source_report.week_start.date()
    target_date = target_week_start + dt.timedelta(days=DAY_OFFSETS[target_day])

    with transaction.atomic():
        target_report = (
            WeeklyReport.objects.select_for_update()
            .filter(student=target_student, week_start__date=target_week_start)
            .first()
        )
        if target_report is None:
            target_report = WeeklyReport.objects.create(
                student=target_student,
                week_start=_midnight(target_week_start),
                week_end=_midnight(target_week_start + dt.timedelta(days=6))
                + dt.timedelta(hours=23, minutes=59, seconds=59),
                disabled_days="",
                important_events="",
                logs=[],
            )

        old_box_ids = list(
            target_report.details.filter(
                day_of_week__in={target_day, target_day.replace("\u200c", "")}
            ).values_list("box_id", flat=True)
        )
        target_report.details.filter(
            day_of_week__in={target_day, target_day.replace("\u200c", "")}
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
        {"status": "success", "copied_details_count": len(source_details)}
    )
