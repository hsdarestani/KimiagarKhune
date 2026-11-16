from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

from plans import lesson_catalog, weekly_plans_v2
from plans.models import DefaultEvent, WeeklyReport, WeeklyReportDetail
from plans.weekly_plans import _parse_clock


def _sync_recurring_events(student_id: int, payload: dict) -> None:
    """Keep current recurring classes in sync with the saved weekly layout.

    Old class slots become inactive instead of lingering in future weeks.
    Historical WeeklyReport data and inactive event rows are preserved.
    """
    desired = set()
    submitted_days = set()
    for day_name, _is_disabled, tasks in weekly_plans_v2._normalized_days(payload):
        submitted_days.add(day_name)
        for task in tasks:
            if not isinstance(task, dict):
                continue
            if str(task.get("box_type") or "مطالعه").strip() != "ایونت":
                continue
            start_time = _parse_clock(task.get("start"))
            end_time = _parse_clock(task.get("end"))
            if start_time is None or end_time is None:
                continue
            desired.add((
                str(task.get("title") or "").strip() or "ایونت",
                day_name,
                start_time,
                end_time,
            ))

    retained_ids = []
    for name, day_name, start_time, end_time in sorted(desired):
        event, created = DefaultEvent.objects.get_or_create(
            student_id=student_id,
            name=name,
            day_of_week=day_name,
            start_time=start_time,
            end_time=end_time,
            defaults={"is_active": True},
        )
        if not created and not event.is_active:
            event.is_active = True
            event.save(update_fields=["is_active"])
        retained_ids.append(event.pk)

    # Each submitted day is authoritative, even when all its events were removed.
    # Partial-day saves leave recurring events on other days untouched.
    DefaultEvent.objects.filter(
        student_id=student_id, day_of_week__in=submitted_days
    ).exclude(pk__in=retained_ids).update(is_active=False)

@login_required
@require_POST
@transaction.atomic
def save_weekly_report(request: HttpRequest):
    """Save the week and promote every event/class to a recurring definition."""

    response = weekly_plans_v2.save_weekly_report(request)
    if response.status_code != 200:
        return response

    payload = json.loads(request.body or "{}")
    student_id = int(payload["student_id"])
    _sync_recurring_events(student_id, payload)
    return response


@login_required
def get_default_events(request: HttpRequest):
    """Return only the current timetable, never stale past school classes.

    After a student has recurring definitions, even inactive ones, those are
    authoritative: old saved weeks cannot bring deactivated classes back.
    """
    response = lesson_catalog.get_default_events(request)
    if response.status_code != 200:
        return response

    student_id = int(request.GET["student_id"])
    known = DefaultEvent.objects.filter(student_id=student_id)
    if known.exists():
        return JsonResponse(
            [
                {
                    "name": event.name,
                    "day_of_week": event.day_of_week,
                    "start_time": event.start_time.strftime("%H:%M"),
                    "end_time": event.end_time.strftime("%H:%M"),
                }
                for event in known.filter(is_active=True).order_by(
                    "day_of_week", "start_time", "pk"
                )
            ],
            safe=False,
        )

    # Legacy migration: use the latest saved week, not an arbitrary old week
    # containing event boxes. A more recent eventless week means no classes.
    latest_report = (
        WeeklyReport.objects.filter(student_id=student_id)
        .order_by("-week_start", "-pk")
        .first()
    )
    if latest_report is None:
        return response

    details = (
        WeeklyReportDetail.objects.select_related("box")
        .filter(report=latest_report, box__box_type__name="ایونت")
        .order_by("start_time", "pk")
    )
    data = []
    seen = set()
    for detail in details:
        item = {
            "name": detail.box.name or "ایونت",
            "day_of_week": detail.day_of_week,
            "start_time": detail.start_time.strftime("%H:%M"),
            "end_time": detail.end_time.strftime("%H:%M"),
        }
        key = tuple(item.values())
        if key not in seen:
            data.append(item)
            seen.add(key)
    return JsonResponse(data, safe=False)
