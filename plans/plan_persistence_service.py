from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

from plans import lesson_catalog, weekly_plans_v2
from plans.models import DefaultEvent, WeeklyReportDetail
from plans.weekly_plans import _parse_clock


def _sync_recurring_events(student_id: int, payload: dict) -> None:
    """Persist event/class boxes so they are available in every future week.

    Weekly plans are week-specific, while classes/events are recurring defaults.
    The v2 saver intentionally stores report boxes as non-default rows, so without
    this synchronization a class created in one week disappears in the next one.
    """

    for day_name, _is_disabled, tasks in weekly_plans_v2._normalized_days(payload):
        for task in tasks:
            if not isinstance(task, dict):
                continue
            box_type = str(task.get("box_type") or "مطالعه").strip()
            if box_type != "ایونت":
                continue

            title = str(task.get("title") or "").strip() or "ایونت"
            start_time = _parse_clock(task.get("start"))
            end_time = _parse_clock(task.get("end"))
            if start_time is None or end_time is None:
                # The canonical saver validates these values before this helper
                # runs, but keep this guard so recurrence can never break saving.
                continue

            event, created = DefaultEvent.objects.get_or_create(
                student_id=student_id,
                name=title,
                day_of_week=day_name,
                start_time=start_time,
                end_time=end_time,
                defaults={"is_active": True},
            )
            if not created and not event.is_active:
                event.is_active = True
                event.save(update_fields=["is_active"])


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
    """Return recurring events plus compatible events saved before this fix.

    The canonical endpoint returns active DefaultEvent rows (and very old legacy
    defaults). We additionally merge the most recent v2 week containing events,
    because v2 stored those event boxes as ``is_default=False``. This lets
    already-defined classes start repeating without forcing the advisor to save
    the old week again.
    """

    response = lesson_catalog.get_default_events(request)
    if response.status_code != 200:
        return response

    try:
        existing = json.loads(response.content.decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError):
        existing = []
    if not isinstance(existing, list):
        existing = []

    student_id = request.GET.get("student_id")
    if not student_id:
        return response

    latest_report_id = (
        WeeklyReportDetail.objects.filter(
            report__student_id=student_id,
            box__box_type__name="ایونت",
            box__is_default=False,
        )
        .order_by("-report__week_start", "-report_id", "-pk")
        .values_list("report_id", flat=True)
        .first()
    )
    if latest_report_id is None:
        return response

    details = (
        WeeklyReportDetail.objects.select_related("box")
        .filter(
            report_id=latest_report_id,
            box__box_type__name="ایونت",
            box__is_default=False,
        )
        .order_by("start_time", "pk")
    )

    data = list(existing)
    seen = {
        (
            str(item.get("name") or ""),
            str(item.get("day_of_week") or ""),
            str(item.get("start_time") or ""),
            str(item.get("end_time") or ""),
        )
        for item in data
        if isinstance(item, dict)
    }
    for detail in details:
        item = {
            "name": detail.box.name or "ایونت",
            "day_of_week": detail.day_of_week,
            "start_time": detail.start_time.strftime("%H:%M"),
            "end_time": detail.end_time.strftime("%H:%M"),
        }
        key = (
            item["name"],
            item["day_of_week"],
            item["start_time"],
            item["end_time"],
        )
        if key in seen:
            continue
        seen.add(key)
        data.append(item)

    return JsonResponse(data, safe=False)
