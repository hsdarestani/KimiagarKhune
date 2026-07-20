from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render

from accounts.models import Advisor, Profile, Student
from plans.models import Lesson


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
GRADE_ORDER = {
    "دوازدهم": 0,
    "یازدهم": 1,
    "دهم": 2,
}


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
        GRADE_ORDER.get(lesson.grade.name, 999),
        lesson.name,
        lesson.pk,
    )


def sort_lessons_for_student(student: Student) -> dict[str, list[Lesson]]:
    major_name = student.major.name
    major_code = MAJOR_TO_CODE.get(major_name)
    if not major_code:
        return {"specialized_lessons": [], "general_lessons": []}

    lessons = (
        Lesson.objects.select_related("grade", "lesson_type")
        .prefetch_related("chapter_set")
        .all()
    )
    specialized_lessons: list[Lesson] = []
    general_lessons: list[Lesson] = []

    for lesson in lessons:
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


@login_required
def plan_view(request):
    if request.user.is_staff:
        students = Student.objects.select_related("profile", "major", "grade").all()
    else:
        try:
            profile = request.user.profile
        except (AttributeError, Profile.DoesNotExist):
            profile = None
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

    return render(
        request,
        "plans/plan.html",
        {
            "students": students,
            "specialized_lessons": lessons["specialized_lessons"],
            "general_lessons": lessons["general_lessons"],
            "major_code": major_code,
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
        }
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
