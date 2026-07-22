from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render

from accounts.models import Advisor, Grade, Profile, Student
from plans.default_plan_data import DEFAULT_BOXES
from plans.models import Box, DefaultEvent, Lesson, WeeklyReportDetail


MAJOR_TO_CODE = {
    "تجربی": "T",
    "ریاضی": "R",
    "انسانی": "E",
}
MAJOR_SUBJECTS = {
    "تجربی": ["زیست", "ریاضی", "شیمی", "فیزیک", "زمین"],
    "ریاضی": ["حسابان", "ریاضی", "آمار", "شیمی", "گسسته", "فیزیک", "هندسه"],
    "انسانی": [
        "جامعه شناسی",
        "فلسفه",
        "عربی",
        "ریاضی",
        "آمار",
        "روانشناسی",
        "اقتصاد",
        "علوم و فنون",
        "منطق",
        "تاریخ",
        "جغرافیا",
    ],
}
GENERAL_SUBJECTS = [
    "ادبیات",
    "عربی",
    "دینی",
    "زبان",
    "نگارش",
    "سلامت و بهداشت",
    "هویت",
    "جغرافیا",
    "زمین",
]
GRADE_SEQUENCE = ("دهم", "یازدهم", "دوازدهم")
GRADE_ORDER = {
    "دوازدهم": 0,
    "یازدهم": 1,
    "دهم": 2,
}


def _normalized_name(value: object) -> str:
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


GRADE_BY_KEY = {_normalized_name(name): name for name in GRADE_SEQUENCE}


def canonical_grade_name(value: object) -> str | None:
    return GRADE_BY_KEY.get(_normalized_name(value))


def allowed_grade_names(student: Student) -> set[str]:
    """Return the student's current grade and all completed lower grades.

    A tenth-grade student sees only tenth-grade lessons. An eleventh-grade
    student sees tenth and eleventh grade. A twelfth-grade student sees all
    three grades. Lessons from a future grade are never returned by the API.
    """

    current = canonical_grade_name(student.grade.name)
    if current is None:
        return {student.grade.name}
    current_index = GRADE_SEQUENCE.index(current)
    return set(GRADE_SEQUENCE[: current_index + 1])


def _track_codes(lesson: Lesson) -> set[str]:
    codes: set[str] = set()
    chapters = lesson.chapter_set.all()
    for chapter in chapters:
        codes.update(
            code.strip().upper()
            for code in (chapter.track or "").split(",")
            if code.strip()
        )
    return codes


def _subject_order(subjects: list[str], lesson: Lesson) -> tuple[int, int, str, int]:
    try:
        subject_index = subjects.index(lesson.name)
    except ValueError:
        subject_index = 999
    return (
        subject_index,
        GRADE_ORDER.get(canonical_grade_name(lesson.grade.name) or lesson.grade.name, 999),
        lesson.name,
        lesson.pk,
    )


def _request_profile(request) -> Profile | None:
    try:
        return request.user.profile
    except (AttributeError, Profile.DoesNotExist):
        return None


def _student_is_visible(request, student: Student) -> bool:
    if request.user.is_staff:
        return True
    profile = _request_profile(request)
    advisor = Advisor.objects.filter(profile=profile).first() if profile else None
    return bool(advisor and student.advisor_id == advisor.pk)


def sort_lessons_for_student(student: Student) -> dict[str, list[Lesson]]:
    major_name = student.major.name
    major_code = MAJOR_TO_CODE.get(major_name)
    if not major_code:
        return {"specialized_lessons": [], "general_lessons": []}

    allowed_grades = allowed_grade_names(student)
    lessons = (
        Lesson.objects.select_related("grade", "lesson_type")
        .prefetch_related("chapter_set")
        .all()
    )
    specialized_lessons: list[Lesson] = []
    general_lessons: list[Lesson] = []

    for lesson in lessons:
        lesson_grade = canonical_grade_name(lesson.grade.name) or lesson.grade.name
        if lesson_grade not in allowed_grades:
            continue
        if major_code not in _track_codes(lesson):
            continue
        if lesson.lesson_type.name == "اختصاصی":
            specialized_lessons.append(lesson)
        else:
            general_lessons.append(lesson)

    specialized_lessons.sort(
        key=lambda lesson: _subject_order(MAJOR_SUBJECTS.get(major_name, []), lesson)
    )
    general_lessons.sort(key=lambda lesson: _subject_order(GENERAL_SUBJECTS, lesson))

    return {
        "specialized_lessons": specialized_lessons,
        "general_lessons": general_lessons,
    }


def _serialize_lessons(lessons: list[Lesson]) -> list[dict[str, object]]:
    return [
        {
            "id": lesson.id,
            "name": lesson.name,
            "grade_id": lesson.grade_id,
            "grade": str(lesson.grade),
        }
        for lesson in lessons
    ]


def _grade_filter_payload(student: Student) -> dict[str, object]:
    allowed_names = allowed_grade_names(student)
    grade_objects = list(Grade.objects.all())
    grade_by_name = {
        canonical_grade_name(grade.name) or grade.name: grade for grade in grade_objects
    }
    grade_options = []
    allowed_grade_ids = []
    for grade_name in GRADE_SEQUENCE:
        grade = grade_by_name.get(grade_name)
        if grade is None:
            continue
        allowed = grade_name in allowed_names
        grade_options.append(
            {
                "id": grade.pk,
                "name": grade_name,
                "allowed": allowed,
                "current": grade.pk == student.grade_id,
            }
        )
        if allowed:
            allowed_grade_ids.append(grade.pk)

    return {
        "student_id": student.pk,
        "student_grade_id": student.grade_id,
        "student_grade": canonical_grade_name(student.grade.name) or student.grade.name,
        "allowed_grade_ids": allowed_grade_ids,
        "grade_options": grade_options,
    }


@login_required
def plan_view(request):
    profile = _request_profile(request)
    if request.user.is_staff:
        students = Student.objects.select_related("profile", "major", "grade").all()
    else:
        advisor = Advisor.objects.filter(profile=profile).first() if profile else None
        students = (
            Student.objects.select_related("profile", "major", "grade").filter(
                advisor=advisor
            )
            if advisor
            else Student.objects.none()
        )

    first_student = students.first()
    if first_student:
        lessons = sort_lessons_for_student(first_student)
        major_code = MAJOR_TO_CODE.get(first_student.major.name, "")
    else:
        lessons = {"specialized_lessons": [], "general_lessons": []}
        major_code = ""

    if profile:
        consultant_name = profile.get_full_name()
    else:
        consultant_name = (
            request.user.get_full_name().strip() or request.user.get_username()
        )

    return render(
        request,
        "plans/plan.html",
        {
            "students": students,
            "specialized_lessons": lessons["specialized_lessons"],
            "general_lessons": lessons["general_lessons"],
            "major_code": major_code,
            "consultant_name": consultant_name,
        },
    )


@login_required
def get_lessons_for_student(request):
    student_id = request.GET.get("student_id")
    if not student_id:
        return HttpResponseBadRequest("Missing student_id parameter.")

    try:
        student = Student.objects.select_related("major", "grade").get(pk=student_id)
    except Student.DoesNotExist:
        return HttpResponseBadRequest("Student not found.")

    if not _student_is_visible(request, student):
        return JsonResponse({"error": "Permission denied"}, status=403)

    major_code = MAJOR_TO_CODE.get(student.major.name)
    if not major_code:
        return HttpResponseBadRequest("Unknown student major.")

    lessons = sort_lessons_for_student(student)
    return JsonResponse(
        {
            "major_code": major_code,
            "specialized_lessons": _serialize_lessons(
                lessons["specialized_lessons"]
            ),
            "general_lessons": _serialize_lessons(lessons["general_lessons"]),
            **_grade_filter_payload(student),
        }
    )


@login_required
def get_default_boxes(request):
    boxes_by_name = {
        box.name: box
        for box in Box.objects.select_related("box_type").filter(
            is_default=True,
            lesson__isnull=True,
            chapter__isnull=True,
        )
        if box.name
    }

    event_boxes = []
    exam_boxes = []
    for definition in DEFAULT_BOXES:
        box = boxes_by_name.get(definition["name"])
        if box is None:
            continue
        payload = {
            "id": box.pk,
            "name": box.name,
            "box_type": box.box_type.name,
            "duration_minutes": box.duration_minutes or definition["duration_minutes"],
            "kind": definition["kind"],
        }
        if definition["kind"] == "exam":
            exam_boxes.append(payload)
        else:
            event_boxes.append(payload)

    return JsonResponse(
        {
            "event_boxes": event_boxes,
            "exam_boxes": exam_boxes,
        }
    )


@login_required
def get_default_events(request):
    student_id = request.GET.get("student_id")
    if not student_id:
        return JsonResponse({"error": "Missing student_id"}, status=400)

    try:
        student = Student.objects.get(pk=student_id)
    except Student.DoesNotExist:
        return JsonResponse({"error": "Student not found"}, status=400)

    if not _student_is_visible(request, student):
        return JsonResponse({"error": "Permission denied"}, status=403)

    events = list(
        DefaultEvent.objects.filter(student=student, is_active=True).order_by(
            "day_of_week", "start_time", "pk"
        )
    )
    if events:
        return JsonResponse(
            [
                {
                    "name": event.name,
                    "day_of_week": event.day_of_week,
                    "start_time": event.start_time.strftime("%H:%M"),
                    "end_time": event.end_time.strftime("%H:%M"),
                }
                for event in events
            ],
            safe=False,
        )

    legacy_details = (
        WeeklyReportDetail.objects.select_related("report", "box")
        .filter(
            report__student=student,
            box__box_type__name="ایونت",
            box__is_default=True,
        )
        .order_by("-report__week_start", "start_time")
    )
    latest_detail = legacy_details.first()
    if latest_detail is None:
        return JsonResponse([], safe=False)

    return JsonResponse(
        [
            {
                "name": detail.box.name,
                "day_of_week": detail.day_of_week,
                "start_time": detail.start_time.strftime("%H:%M"),
                "end_time": detail.end_time.strftime("%H:%M"),
            }
            for detail in legacy_details.filter(report_id=latest_detail.report_id)
        ],
        safe=False,
    )


@login_required
def move_lesson_to_end(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    lesson_id = request.POST.get("lesson_id")
    student_id = request.POST.get("student_id")
    if not lesson_id or not student_id:
        return JsonResponse({"error": "Missing lesson_id or student_id"}, status=400)

    try:
        selected_id = int(lesson_id)
        student = Student.objects.select_related("major", "grade").get(pk=student_id)
    except (TypeError, ValueError, Student.DoesNotExist):
        return JsonResponse({"error": "Invalid lesson or student"}, status=400)

    if not _student_is_visible(request, student):
        return JsonResponse({"error": "Permission denied"}, status=403)

    lessons = sort_lessons_for_student(student)
    for key in ("specialized_lessons", "general_lessons"):
        collection = lessons[key]
        selected = next((lesson for lesson in collection if lesson.id == selected_id), None)
        if selected is not None:
            collection.remove(selected)
            collection.append(selected)
            break

    return JsonResponse(
        {
            "specialized": _serialize_lessons(lessons["specialized_lessons"]),
            "general": _serialize_lessons(lessons["general_lessons"]),
        }
    )
