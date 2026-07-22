from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import Advisor, Grade, Major, Profile, School, Student
from plans.views import (
    availability_error_message,
    create_advisor_availability_slot,
    serialize_advisors_with_schedule,
)


def _create_unusable_user(username: str) -> User:
    user = User(username=username)
    user.set_unusable_password()
    user.save()
    return user


@require_POST
@login_required
@transaction.atomic
def add_student_view(request):
    if not request.user.is_staff:
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON.")

    required = ("first_name", "last_name", "phone_number", "major_id", "grade_id")
    if any(not str(data.get(field, "")).strip() for field in required):
        return JsonResponse(
            {"status": "error", "message": "تمام فیلدهای الزامی را تکمیل کنید."},
            status=400,
        )

    phone_number = str(data["phone_number"]).strip()
    if User.objects.filter(username=phone_number).exists():
        return JsonResponse(
            {"status": "error", "message": "کاربری با این شماره موبایل از قبل وجود دارد."},
            status=400,
        )

    try:
        major = Major.objects.get(pk=data["major_id"])
        grade = Grade.objects.get(pk=data["grade_id"])
    except (Major.DoesNotExist, Grade.DoesNotExist, TypeError, ValueError):
        return JsonResponse(
            {"status": "error", "message": "رشته یا پایه انتخاب‌شده معتبر نیست."},
            status=400,
        )

    school, _ = School.objects.get_or_create(name="مدرسه پیش‌فرض")
    user = _create_unusable_user(phone_number)
    profile = Profile.objects.create(
        user=user,
        role="student",
        first_name=str(data["first_name"]).strip(),
        last_name=str(data["last_name"]).strip(),
        phone_number=phone_number,
        email=(str(data.get("email") or "").strip() or None),
    )
    student = Student.objects.create(
        profile=profile,
        major=major,
        grade=grade,
        school=school,
    )

    return JsonResponse(
        {
            "status": "success",
            "message": "دانش‌آموز با موفقیت ایجاد شد.",
            "student_id": student.pk,
            "user_id": user.pk,
        },
        status=201,
    )


@login_required
@require_http_methods(["GET", "POST"])
def admin_advisors_view(request):
    if not request.user.is_staff:
        return JsonResponse({"error": "Permission denied"}, status=403)

    if request.method == "GET":
        advisors = Advisor.objects.select_related("profile").prefetch_related("availabilities")
        return JsonResponse({"advisors": serialize_advisors_with_schedule(advisors)})

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON.")

    required = ("first_name", "last_name", "phone_number")
    if any(not str(payload.get(field, "")).strip() for field in required):
        return JsonResponse(
            {
                "status": "error",
                "message": "لطفاً نام، نام خانوادگی و شماره موبایل مشاور را تکمیل کنید.",
            },
            status=400,
        )

    phone_number = str(payload["phone_number"]).strip()
    if User.objects.filter(username=phone_number).exists():
        return JsonResponse(
            {"status": "error", "message": "کاربری با این شماره موبایل از قبل وجود دارد."},
            status=400,
        )

    try:
        with transaction.atomic():
            user = _create_unusable_user(phone_number)
            profile = Profile.objects.create(
                user=user,
                role="advisor",
                first_name=str(payload["first_name"]).strip(),
                last_name=str(payload["last_name"]).strip(),
                phone_number=phone_number,
                email=(str(payload.get("email") or "").strip() or None),
                telegram_chat_id=(str(payload.get("telegram_chat_id") or "").strip() or None),
            )
            advisor = Advisor.objects.create(profile=profile)
            for slot_payload in payload.get("working_hours") or []:
                try:
                    create_advisor_availability_slot(advisor, slot_payload)
                except ValueError as exc:
                    raise ValueError(str(exc)) from exc
                except IntegrityError as exc:
                    raise ValueError("duplicate") from exc
    except ValueError as exc:
        return JsonResponse(
            {"status": "error", "message": availability_error_message(str(exc))},
            status=400,
        )
    except IntegrityError:
        return JsonResponse(
            {"status": "error", "message": "ثبت مشاور با خطا مواجه شد."},
            status=400,
        )

    return JsonResponse(
        {
            "status": "success",
            "advisor": serialize_advisors_with_schedule([advisor])[0],
        },
        status=201,
    )
