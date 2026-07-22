from __future__ import annotations

import os
import sys
from urllib.parse import urljoin

from playwright.sync_api import Locator, Page, sync_playwright


BASE_URL = os.environ.get(
    "PLAN_BASE_URL", "https://panel.kimiagarkhoone.com"
).rstrip("/") + "/"
USERNAME = os.environ.get("PLAN_USERNAME", "").strip()
PASSWORD = os.environ.get("PLAN_PASSWORD", "")
TEST_WEEK = os.environ.get("PLAN_GRID_TEST_WEEK", "1405-09-01")
STUDENT_LABEL = os.environ.get(
    "PLAN_GRID_STUDENT_LABEL", "نمونه ریاضی یازدهم"
)
HOUR_HEIGHT = 35.0
QUARTER_HEIGHT = 8.75
GRID_HEIGHT = 630.0


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def relative_top(task: Locator, container: Locator) -> float:
    task_box = task.bounding_box()
    container_box = container.bounding_box()
    if not task_box or not container_box:
        raise AssertionError("Could not read task/container geometry")
    return task_box["y"] - container_box["y"]


def drag_palette_to(
    page: Page,
    source: Locator,
    target: Locator,
    desired_top: float,
) -> None:
    source.scroll_into_view_if_needed()
    source_box = source.bounding_box()
    target_box = target.bounding_box()
    if not source_box or not target_box:
        raise AssertionError("Palette or target is not visible")

    page.mouse.move(
        source_box["x"] + source_box["width"] / 2,
        source_box["y"] + source_box["height"] / 2,
    )
    page.mouse.down()
    page.mouse.move(
        source_box["x"] + source_box["width"] / 2 + 6,
        source_box["y"] + source_box["height"] / 2 + 6,
        steps=3,
    )
    page.mouse.move(
        target_box["x"] + target_box["width"] / 2,
        target_box["y"] + desired_top,
        steps=28,
    )
    page.mouse.up()
    page.wait_for_timeout(350)


def load_week(page: Page) -> None:
    page.select_option("#student-select", label=STUDENT_LABEL)
    page.evaluate(
        """
        value => {
          window.jQuery('#weekSelector')
            .val(value)
            .trigger('input')
            .trigger('change');
        }
        """,
        TEST_WEEK,
    )
    page.click("#loadWeek")
    page.wait_for_function(
        "window.planRuntimeState && window.planRuntimeState.loaded && "
        "!window.planRuntimeState.loading",
        timeout=30_000,
    )
    page.wait_for_function(
        "window.planTimeGrid && "
        "document.body.dataset.planTimeGridVersion && "
        "document.querySelectorAll('.calendar .plan-day-header').length === 7",
        timeout=15_000,
    )
    page.wait_for_function(
        "window.planLessonToolbarState && "
        "String(window.planLessonToolbarState.studentGrade) === 'یازدهم' && "
        "document.body.dataset.planLessonToolbarReady === 'true'",
        timeout=15_000,
    )
    page.evaluate("window.planTimeGrid.synchronize()")
    page.wait_for_timeout(150)


def main() -> int:
    if not USERNAME or not PASSWORD:
        print("PLAN_USERNAME and PLAN_PASSWORD are required.", file=sys.stderr)
        return 2

    page_errors: list[str] = []
    dialogs: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            locale="fa-IR",
            viewport={"width": 1800, "height": 1050},
        )
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        def accept_dialog(dialog) -> None:
            dialogs.append(dialog.message)
            dialog.accept()

        page.on("dialog", accept_dialog)
        page.goto(
            urljoin(BASE_URL, "login/"),
            wait_until="domcontentloaded",
            timeout=30_000,
        )
        page.fill("#username", USERNAME)
        page.fill("#password", PASSWORD)
        page.click('form button[type="submit"]')
        page.wait_for_url("**/plan/", timeout=30_000)
        page.wait_for_function("window.jQuery && window.jQuery.ui", timeout=20_000)
        load_week(page)

        snapshot = page.evaluate("window.planTimeGrid.geometrySnapshot()")
        require(snapshot is not None, "time grid exposes a geometry snapshot")
        require(
            abs(snapshot["gridHeight"] - GRID_HEIGHT) <= 1.5,
            "day grid has the authoritative 18-hour height",
        )
        require(
            abs(snapshot["sixCenter"] - snapshot["gridTop"]) <= 1.5,
            "06:00 axis mark and day-grid origin are identical",
        )
        require(
            abs(snapshot["hourDistance"] - HOUR_HEIGHT) <= 1.0,
            "timeline hour marks are exactly 35 pixels apart",
        )

        school_tasks = page.locator(".calendar .calendar-task").filter(
            has=page.locator('.task-title[value="مدرسه"], .task-title:text-is("مدرسه")')
        )
        if school_tasks.count() == 0:
            school_tasks = page.locator(".calendar .calendar-task").filter(
                has_text="مدرسه"
            )
        require(school_tasks.count() >= 5, "default school blocks are loaded")

        school = school_tasks.first
        school_container = school.locator("xpath=parent::*")
        school_box = school.bounding_box()
        require(school_box is not None, "school block geometry is readable")
        require(
            abs(relative_top(school, school_container) - 52.5) <= 2.0,
            "07:30 school start aligns halfway between 07:00 and 08:00",
        )
        require(
            abs(school_box["height"] - 227.5) <= 2.0,
            "07:30–14:00 school duration uses the same time scale",
        )
        require(
            "07:30" in school.locator(".time-label").inner_text()
            and "14:00" in school.locator(".time-label").inner_text(),
            "school time label matches its visual position and height",
        )

        toolbar = page.evaluate(
            """
            () => ({
              studentGrade: window.planLessonToolbarState.studentGrade,
              majorCode: window.planLessonToolbarState.majorCode,
              allowedIds: window.planLessonToolbarState.allowedGradeIds,
              options: window.planLessonToolbarState.gradeOptions,
              visibleGrades: Array.from(document.querySelectorAll(
                '#specialized-task-list .task:visible, #general-task-list .task:visible'
              )).map(item => String(item.dataset.grade || '')),
              allGrades: Array.from(document.querySelectorAll(
                '#specialized-task-list .task, #general-task-list .task'
              )).map(item => String(item.dataset.grade || '')),
              visibleText: Array.from(document.querySelectorAll(
                '#specialized-task-list .task, #general-task-list .task'
              )).filter(item => getComputedStyle(item).display !== 'none')
                .map(item => item.textContent.trim())
            })
            """
        )
        allowed_ids = {str(value) for value in toolbar["allowedIds"]}
        allowed_names = {
            option["name"]
            for option in toolbar["options"]
            if str(option["id"]) in allowed_ids
        }
        require(toolbar["studentGrade"] == "یازدهم", "selected student grade is یازدهم")
        require(toolbar["majorCode"] == "R", "selected student major is ریاضی")
        require(
            allowed_names == {"دهم", "یازدهم"},
            "eleventh-grade toolbar enables only tenth and eleventh grades",
        )
        require(
            set(toolbar["allGrades"]).issubset(allowed_ids),
            "future-grade lessons are absent from the toolbar data",
        )
        require(
            set(toolbar["visibleGrades"]).issubset(allowed_ids),
            "visible lesson cards obey enabled grade filters",
        )
        require(
            not any("دوازدهم" in text for text in toolbar["visibleText"]),
            "twelfth-grade lessons are not shown to an eleventh-grade student",
        )
        require(
            not any("زیست" in text for text in toolbar["visibleText"]),
            "math student toolbar excludes experimental-major lessons",
        )

        containers = page.locator(".calendar .task-container")
        free_container = None
        for index in range(containers.count()):
            candidate = containers.nth(index)
            school_count = candidate.locator(".calendar-task").filter(
                has_text="مدرسه"
            ).count()
            if school_count == 0:
                free_container = candidate
                break
        require(free_container is not None, "a non-school day is available for drop testing")

        lesson_palette = page.locator(
            ".subjects-box .plan-lesson-palette:visible"
        ).first
        require(lesson_palette.count() == 1, "an allowed lesson is visible in the toolbar")
        drag_palette_to(page, lesson_palette, free_container, 210.0)

        study = free_container.locator(
            '.calendar-task[data-box-type="مطالعه"]'
        ).first
        require(study.count() == 1, "lesson can be dropped at the 12:00 row")
        require(
            abs(relative_top(study, free_container) - 210.0) <= QUARTER_HEIGHT + 1.0,
            "study box visual top matches the 12:00 timeline position",
        )
        label = study.locator(".time-label").inner_text().strip()
        require(
            "12:00" in label and "13:30" in label,
            "study time label is synchronized with its grid position",
        )

        require(
            not any("برنامه آینده" in message for message in dialogs),
            "grid test week is not blocked by a future-report dialog",
        )
        require(
            not page_errors,
            "time-grid and lesson-toolbar flow has no uncaught JavaScript errors: "
            + " | ".join(page_errors),
        )

        context.close()
        browser.close()

    print("Plan time-grid and lesson-toolbar regression completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
