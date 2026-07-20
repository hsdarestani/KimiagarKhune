from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.models import Advisor, Grade, Major, Profile, School, Student
from plans.models import Box, BoxType, DefaultEvent


DEFAULT_BOX_TYPES = ("مطالعه", "ایونت", "تکلیف", "شناور")

DEFAULT_BOXES = (
    {"name": "ایونت", "box_type": "ایونت", "duration_minutes": 90, "kind": "event"},
    {"name": "باکس شناور", "box_type": "شناور", "duration_minutes": 90, "kind": "floating"},
    {"name": "آزمون آزمایشی", "box_type": "ایونت", "duration_minutes": 210, "kind": "exam"},
    {"name": "تحلیل آزمون", "box_type": "ایونت", "duration_minutes": 240, "kind": "exam"},
    {"name": "پیش آزمون و تحلیل آن", "box_type": "ایونت", "duration_minutes": 360, "kind": "exam"},
    {"name": "مرور و آمادگی آزمون", "box_type": "ایونت", "duration_minutes": 240, "kind": "exam"},
)

DEMO_STUDENTS = (
    {
        "username": "demo_plan_student_t",
        "first_name": "نمونه",
        "last_name": "تجربی دوازدهم",
        "major": "تجربی",
        "grade": "دوازدهم",
    },
    {
        "username": "demo_plan_student_r",
        "first_name": "نمونه",
        "last_name": "ریاضی یازدهم",
        "major": "ریاضی",
        "grade": "یازدهم",
    },
    {
        "username": "demo_plan_student_e",
        "first_name": "نمونه",
        "last_name": "انسانی دهم",
        "major": "انسانی",
        "grade": "دهم",
    },
)

DEFAULT_SCHOOL_DAYS = ("شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه")


@dataclass(frozen=True)
class DefaultPlanSummary:
    box_types_created: int
    boxes_created: int
    boxes_updated: int
    students_created: int
    students_updated: int
    events_created: int


def _ensure_inactive_user(username: str, *, using: str):
    User = get_user_model()
    user, created = User.objects.using(using).get_or_create(
        username=username,
        defaults={"is_active": False},
    )
    if created:
        user.set_unusable_password()
        user.save(using=using, update_fields=["password", "is_active"])
    return user, created


def ensure_advisor_for_user(user, *, using: str = "default") -> Advisor:
    profile, _ = Profile.objects.using(using).get_or_create(
        user=user,
        defaults={
            "role": "advisor",
            "first_name": user.first_name or user.username,
            "last_name": user.last_name or "",
            "email": user.email or None,
        },
    )
    return Advisor.objects.using(using).get_or_create(profile=profile)[0]


def _resolve_advisor(*, using: str, advisor: Advisor | None) -> Advisor:
    if advisor is not None:
        return Advisor.objects.using(using).get(pk=advisor.pk)

    existing = (
        Advisor.objects.using(using)
        .select_related("profile__user")
        .order_by("-profile__user__is_staff", "pk")
        .first()
    )
    if existing is not None:
        return existing

    user, _ = _ensure_inactive_user("demo_plan_advisor", using=using)
    profile, _ = Profile.objects.using(using).get_or_create(
        user=user,
        defaults={
            "role": "advisor",
            "first_name": "مشاور",
            "last_name": "نمونه",
        },
    )
    return Advisor.objects.using(using).get_or_create(profile=profile)[0]


def seed_plan_defaults(
    *,
    using: str = "default",
    advisor: Advisor | None = None,
) -> DefaultPlanSummary:
    """Seed the plan page's default palette, demo students and recurring events.

    The operation is idempotent and can safely run after every deployment.
    Demo users are inactive and have unusable passwords; they only provide
    visible sample data for staff/advisor planning screens.
    """

    box_types_created = 0
    boxes_created = 0
    boxes_updated = 0
    students_created = 0
    students_updated = 0
    events_created = 0

    with transaction.atomic(using=using):
        box_type_map: dict[str, BoxType] = {}
        for name in DEFAULT_BOX_TYPES:
            box_type, created = BoxType.objects.using(using).get_or_create(
                name=name,
                defaults={"is_default": True},
            )
            if not box_type.is_default:
                box_type.is_default = True
                box_type.save(using=using, update_fields=["is_default"])
            box_type_map[name] = box_type
            box_types_created += int(created)

        for definition in DEFAULT_BOXES:
            queryset = Box.objects.using(using).filter(
                name=definition["name"],
                box_type=box_type_map[definition["box_type"]],
                lesson__isnull=True,
                chapter__isnull=True,
                is_default=True,
            )
            box = queryset.order_by("pk").first()
            if box is None:
                Box.objects.using(using).create(
                    box_type=box_type_map[definition["box_type"]],
                    name=definition["name"],
                    duration_minutes=definition["duration_minutes"],
                    optional_tests_count=0,
                    is_default=True,
                )
                boxes_created += 1
            elif box.duration_minutes != definition["duration_minutes"]:
                box.duration_minutes = definition["duration_minutes"]
                box.save(using=using, update_fields=["duration_minutes"])
                boxes_updated += 1

        assigned_advisor = _resolve_advisor(using=using, advisor=advisor)
        school, _ = School.objects.using(using).get_or_create(
            name="مدرسه نمونه کیمیاگرخونه"
        )

        for definition in DEMO_STUDENTS:
            major, _ = Major.objects.using(using).get_or_create(name=definition["major"])
            grade, _ = Grade.objects.using(using).get_or_create(name=definition["grade"])
            user, _ = _ensure_inactive_user(definition["username"], using=using)
            profile, _ = Profile.objects.using(using).get_or_create(
                user=user,
                defaults={
                    "role": "student",
                    "first_name": definition["first_name"],
                    "last_name": definition["last_name"],
                },
            )

            changed_profile_fields = []
            if profile.role != "student":
                profile.role = "student"
                changed_profile_fields.append("role")
            if profile.first_name != definition["first_name"]:
                profile.first_name = definition["first_name"]
                changed_profile_fields.append("first_name")
            if profile.last_name != definition["last_name"]:
                profile.last_name = definition["last_name"]
                changed_profile_fields.append("last_name")
            if changed_profile_fields:
                profile.save(using=using, update_fields=changed_profile_fields)

            student = Student.objects.using(using).filter(profile=profile).first()
            if student is None:
                student = Student.objects.using(using).create(
                    profile=profile,
                    school=school,
                    major=major,
                    grade=grade,
                    advisor=assigned_advisor,
                )
                students_created += 1
            else:
                changed_student_fields = []
                for field_name, value in (
                    ("school", school),
                    ("major", major),
                    ("grade", grade),
                    ("advisor", assigned_advisor),
                ):
                    if getattr(student, f"{field_name}_id") != value.pk:
                        setattr(student, field_name, value)
                        changed_student_fields.append(field_name)
                if changed_student_fields:
                    student.save(using=using, update_fields=changed_student_fields)
                    students_updated += 1

            for day_name in DEFAULT_SCHOOL_DAYS:
                _, created = DefaultEvent.objects.using(using).get_or_create(
                    student=student,
                    name="مدرسه",
                    day_of_week=day_name,
                    start_time=time(7, 30),
                    end_time=time(14, 0),
                    defaults={"is_active": True},
                )
                events_created += int(created)

    return DefaultPlanSummary(
        box_types_created=box_types_created,
        boxes_created=boxes_created,
        boxes_updated=boxes_updated,
        students_created=students_created,
        students_updated=students_updated,
        events_created=events_created,
    )
