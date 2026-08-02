from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_GET

from accounts.models import Student
from plans.lesson_catalog import MAJOR_TO_CODE, _student_is_visible, sort_lessons_for_student
from plans.models import Chapter, Lesson


def _track_codes(value: object) -> set[str]:
    return {
        code.strip().upper()
        for code in str(value or "").split(",")
        if code.strip()
    }


@login_required
@require_GET
def get_chapters(request):
    """Return the selected lesson's chapters for an authorized student.

    Student grade and major are derived on the server. The browser no longer
    needs to send a potentially stale grade or major code when switching
    between an advisor's students.
    """

    student_id = request.GET.get("student_id")
    lesson_id = request.GET.get("lesson_id")
    query = str(request.GET.get("q") or "").strip()

    if not student_id or not lesson_id:
        return HttpResponseBadRequest("Missing student_id or lesson_id parameter.")

    try:
        student = Student.objects.select_related("major", "grade").get(pk=student_id)
    except (Student.DoesNotExist, TypeError, ValueError):
        return JsonResponse({"error": "دانش‌آموز مورد نظر یافت نشد."}, status=404)

    if not _student_is_visible(request, student):
        return JsonResponse(
            {"error": "دسترسی به این دانش‌آموز مجاز نیست."},
            status=403,
        )

    try:
        lesson = (
            Lesson.objects.select_related("grade", "lesson_type")
            .prefetch_related("chapter_set")
            .get(pk=lesson_id)
        )
    except (Lesson.DoesNotExist, TypeError, ValueError):
        return JsonResponse({"error": "درس مورد نظر یافت نشد."}, status=404)

    allowed_lessons = sort_lessons_for_student(student)
    allowed_ids = {
        item.pk
        for item in (
            allowed_lessons["specialized_lessons"]
            + allowed_lessons["general_lessons"]
        )
    }
    if lesson.pk not in allowed_ids:
        return JsonResponse(
            {"error": "این درس برای پایه یا رشته دانش‌آموز قابل انتخاب نیست."},
            status=403,
        )

    major_code = MAJOR_TO_CODE.get(student.major.name, "").upper()
    chapters = Chapter.objects.filter(lesson=lesson).order_by(
        "chapter_number", "pk"
    )

    seen: set[tuple[object, str]] = set()
    results: list[dict[str, object]] = []
    for chapter in chapters:
        codes = _track_codes(chapter.track)
        if codes and major_code not in codes:
            continue

        label = f"{chapter.chapter_number} - {chapter.name}"
        if query and query not in label:
            continue

        key = (chapter.chapter_number, chapter.name)
        if key in seen:
            continue
        seen.add(key)
        results.append({"id": chapter.pk, "text": label})

    return JsonResponse(results, safe=False)
