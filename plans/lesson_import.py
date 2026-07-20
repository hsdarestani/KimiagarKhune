from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from django.db import transaction

from accounts.models import Grade, Major
from plans.models import Chapter, Lesson, LessonType


DEFAULT_LESSON_GRAPH_PATH = Path(__file__).resolve().parent / "data" / "lesson_graph_1403.csv"

REQUIRED_COLUMNS = {
    "ID درس",
    "اسم درس",
    "شماره فصل",
    "اسم فصل",
    "عمومی/اختصاصی",
    "چه پایه ای",
    "چه رشته ای",
    "زوج درسی",
}
GRADE_NAMES = ("دهم", "یازدهم", "دوازدهم")
MAJOR_NAMES = ("تجربی", "ریاضی", "انسانی")
LESSON_TYPE_NAMES = ("عمومی", "اختصاصی")
TRACK_ORDER = ("T", "R", "E")
TRACK_CODES = set(TRACK_ORDER)


@dataclass(frozen=True)
class ImportSummary:
    rows: int
    grades_created: int
    majors_created: int
    lesson_types_created: int
    lessons_created: int
    lessons_updated: int
    chapters_created: int
    chapters_updated: int


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_track(value: object, *, row_number: int) -> str:
    raw_codes = [_clean(part).upper() for part in str(value or "").split(",")]
    codes = {code for code in raw_codes if code}
    invalid = sorted(codes - TRACK_CODES)
    if invalid:
        raise ValueError(
            f"ردیف {row_number}: کد رشته نامعتبر است: {', '.join(invalid)}"
        )
    if not codes:
        raise ValueError(f"ردیف {row_number}: ستون «چه رشته ای» خالی است.")
    return ",".join(code for code in TRACK_ORDER if code in codes)


def _base_lesson_name(raw_name: str, grade_name: str) -> str:
    suffix = f" {grade_name}"
    if raw_name.endswith(suffix):
        return raw_name[: -len(suffix)].strip()
    return raw_name


def _first_or_create(queryset, *, create_kwargs: dict):
    obj = queryset.order_by("pk").first()
    if obj is not None:
        return obj, False
    return queryset.model.objects.using(queryset.db).create(**create_kwargs), True


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"فایل گراف دروس پیدا نشد: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - fieldnames
        if missing:
            raise ValueError(
                "ستون‌های الزامی فایل موجود نیستند: " + ", ".join(sorted(missing))
            )
        rows = list(reader)

    if not rows:
        raise ValueError("فایل گراف دروس هیچ ردیف داده‌ای ندارد.")
    return rows


def import_lesson_graph(
    path: str | Path = DEFAULT_LESSON_GRAPH_PATH,
    *,
    using: str = "default",
) -> ImportSummary:
    """Import the lesson graph into the legacy Lesson/Chapter schema.

    The import is idempotent. A lesson is identified by subject code, grade,
    lesson type and paired-lesson value. A chapter is identified by lesson,
    chapter number and track code(s), so a later CSV correction updates the
    chapter title instead of creating another row.
    """

    source_path = Path(path)
    rows = _read_rows(source_path)

    grades_created = 0
    majors_created = 0
    lesson_types_created = 0
    lessons_created = 0
    lessons_updated = 0
    chapters_created = 0
    chapters_updated = 0

    grade_map: dict[str, Grade] = {}
    major_map: dict[str, Major] = {}
    lesson_type_map: dict[str, LessonType] = {}
    lesson_cache: dict[tuple[str, str, str, str, str | None], Lesson] = {}

    with transaction.atomic(using=using):
        for grade_name in GRADE_NAMES:
            grade, created = Grade.objects.using(using).get_or_create(name=grade_name)
            grade_map[grade_name] = grade
            grades_created += int(created)

        for major_name in MAJOR_NAMES:
            major, created = Major.objects.using(using).get_or_create(name=major_name)
            major_map[major_name] = major
            majors_created += int(created)

        for lesson_type_name in LESSON_TYPE_NAMES:
            lesson_type, created = LessonType.objects.using(using).get_or_create(
                name=lesson_type_name
            )
            lesson_type_map[lesson_type_name] = lesson_type
            lesson_types_created += int(created)

        for row_number, row in enumerate(rows, start=2):
            subject_code = _clean(row.get("ID درس")).lower()
            raw_lesson_name = _clean(row.get("اسم درس"))
            chapter_name = _clean(row.get("اسم فصل"))
            lesson_type_name = _clean(row.get("عمومی/اختصاصی"))
            grade_name = _clean(row.get("چه پایه ای"))
            paired_lesson = _clean(row.get("زوج درسی")) or None
            track = _normalize_track(row.get("چه رشته ای"), row_number=row_number)

            if not subject_code:
                raise ValueError(f"ردیف {row_number}: ستون «ID درس» خالی است.")
            if not raw_lesson_name:
                raise ValueError(f"ردیف {row_number}: ستون «اسم درس» خالی است.")
            if not chapter_name:
                raise ValueError(f"ردیف {row_number}: ستون «اسم فصل» خالی است.")
            if grade_name not in grade_map:
                raise ValueError(
                    f"ردیف {row_number}: پایه نامعتبر است: {grade_name or 'خالی'}"
                )
            if lesson_type_name not in lesson_type_map:
                raise ValueError(
                    f"ردیف {row_number}: نوع درس نامعتبر است: "
                    f"{lesson_type_name or 'خالی'}"
                )

            try:
                chapter_number = int(_clean(row.get("شماره فصل")))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"ردیف {row_number}: شماره فصل باید عدد صحیح باشد."
                ) from exc
            if chapter_number < 0:
                raise ValueError(f"ردیف {row_number}: شماره فصل نمی‌تواند منفی باشد.")

            lesson_name = _base_lesson_name(raw_lesson_name, grade_name)
            lesson_key = (
                subject_code,
                lesson_name,
                grade_name,
                lesson_type_name,
                paired_lesson,
            )
            lesson = lesson_cache.get(lesson_key)
            if lesson is None:
                lesson_queryset = Lesson.objects.using(using).filter(
                    subject_code=subject_code,
                    grade=grade_map[grade_name],
                    lesson_type=lesson_type_map[lesson_type_name],
                    paired_lesson=paired_lesson,
                )
                lesson, created = _first_or_create(
                    lesson_queryset,
                    create_kwargs={
                        "subject_code": subject_code,
                        "name": lesson_name,
                        "grade": grade_map[grade_name],
                        "lesson_type": lesson_type_map[lesson_type_name],
                        "paired_lesson": paired_lesson,
                    },
                )
                if created:
                    lessons_created += 1
                elif lesson.name != lesson_name:
                    lesson.name = lesson_name
                    lesson.save(update_fields=["name"], using=using)
                    lessons_updated += 1
                lesson_cache[lesson_key] = lesson

            chapter_queryset = Chapter.objects.using(using).filter(
                lesson=lesson,
                chapter_number=chapter_number,
                track=track,
            )
            chapter, created = _first_or_create(
                chapter_queryset,
                create_kwargs={
                    "lesson": lesson,
                    "chapter_number": chapter_number,
                    "name": chapter_name,
                    "track": track,
                },
            )
            if created:
                chapters_created += 1
            elif chapter.name != chapter_name:
                chapter.name = chapter_name
                chapter.save(update_fields=["name"], using=using)
                chapters_updated += 1

    return ImportSummary(
        rows=len(rows),
        grades_created=grades_created,
        majors_created=majors_created,
        lesson_types_created=lesson_types_created,
        lessons_created=lessons_created,
        lessons_updated=lessons_updated,
        chapters_created=chapters_created,
        chapters_updated=chapters_updated,
    )
