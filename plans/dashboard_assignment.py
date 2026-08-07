from __future__ import annotations

import datetime
import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_POST

from accounts.models import Advisor, AdvisorAvailability, Student
from plans.advisor_access import set_current_advisor
from plans.models import Course, Session


@require_POST
@login_required
@transaction.atomic
def assign_student_view(request):
    """Assign a student to an advisor and create the four-session course.

    The dashboard historically created only a Course and forgot to persist the
    Student.advisor FK. Access-control code uses that FK, so the UI could report a
    successful assignment while chat/Plan access still returned 403. The FK is now
    updated in the same database transaction as the course and sessions.
    """

    if not request.user.is_staff:
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON.")

    required = ("student_id", "advisor_id", "day_of_week", "start_time", "start_date")
    if any(data.get(field) in (None, "") for field in required):
        return JsonResponse(
            {"status": "error", "message": "اطلاعات تخصیص کامل نیست."},
            status=400,
        )

    try:
        student = Student.objects.select_for_update().get(pk=data["student_id"])
        advisor = Advisor.objects.get(pk=data["advisor_id"])
        start_date = datetime.datetime.strptime(
            str(data["start_date"]), "%Y-%m-%d"
        ).date()
        start_time = datetime.datetime.strptime(
            str(data["start_time"]), "%H:%M"
        ).time()
    except Student.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "دانش‌آموز مورد نظر یافت نشد."},
            status=404,
        )
    except Advisor.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "مشاور مورد نظر یافت نشد."},
            status=404,
        )
    except (TypeError, ValueError):
        return JsonResponse(
            {"status": "error", "message": "تاریخ یا ساعت تخصیص معتبر نیست."},
            status=400,
        )

    day_of_week = str(data["day_of_week"]).strip()
    availability = AdvisorAvailability.objects.filter(
        advisor=advisor,
        day_of_week=day_of_week,
        start_time=start_time,
    ).first()
    if not availability:
        return JsonResponse(
            {
                "status": "error",
                "message": "برای مشاور انتخاب‌شده در این روز ساعت فعالی ثبت نشده است.",
            },
            status=400,
        )

    existing_assignments = Course.objects.filter(
        advisor=advisor,
        day_of_week=day_of_week,
        start_time=start_time,
        is_active=True,
    ).count()
    if existing_assignments >= availability.max_students:
        return JsonResponse(
            {
                "status": "error",
                "message": "ظرفیت این بازه زمانی برای مشاور انتخاب‌شده تکمیل است.",
            },
            status=400,
        )

    # This is the relationship used by chat, Plan visibility and other access
    # checks. Keep it in the exact same transaction as the course creation.
    set_current_advisor(student, advisor)

    course = Course.objects.create(
        student=student,
        advisor=advisor,
        day_of_week=day_of_week,
        start_time=start_time,
        start_date=start_date,
    )

    Session.objects.bulk_create(
        [
            Session(
                course=course,
                session_number=number,
                date=start_date + datetime.timedelta(days=7 * (number - 1)),
            )
            for number in range(1, 5)
        ]
    )

    return JsonResponse(
        {
            "status": "success",
            "message": "دانش‌آموز با موفقیت تخصیص داده شد.",
            "student_id": student.pk,
            "advisor_id": advisor.pk,
            "course_id": course.pk,
        },
        status=201,
    )
