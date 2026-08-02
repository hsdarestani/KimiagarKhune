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
GRID_PIXELS = 8.75


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def box(locator: Locator) -> dict[str, float]:
    value = locator.bounding_box()
    if not value:
        raise AssertionError("Element has no visible bounding box")
    return value


def drag_palette_to(page: Page, source: Locator, target: Locator, y_offset: float) -> None:
    source.scroll_into_view_if_needed()
    source_box = box(source)
    target_box = box(target)
    page.mouse.move(
        source_box["x"] + source_box["width"] / 2,
        source_box["y"] + source_box["height"] / 2,
    )
    page.mouse.down()
    page.mouse.move(
        source_box["x"] + source_box["width"] / 2 + 7,
        source_box["y"] + source_box["height"] / 2 + 7,
        steps=4,
    )
    page.mouse.move(
        target_box["x"] + target_box["width"] / 2,
        target_box["y"] + y_offset,
        steps=30,
    )
    page.mouse.up()
    page.wait_for_timeout(450)


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
        "window.planChapterLoader && window.planQuarterSnapFeedback && "
        "document.body.dataset.planChapterLoaderVersion && "
        "document.body.dataset.planQuarterSnapVersion",
        timeout=20_000,
    )
    page.wait_for_timeout(250)


def main() -> int:
    if not USERNAME or not PASSWORD:
        print("PLAN_USERNAME and PLAN_PASSWORD are required.", file=sys.stderr)
        return 2

    page_errors: list[str] = []
    failed_requests: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            locale="fa-IR",
            viewport={"width": 1800, "height": 1050},
        )
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("dialog", lambda dialog: dialog.accept())

        def collect_response(response) -> None:
            if response.url.endswith("/get-chapters/") and response.status >= 400:
                failed_requests.append(f"{response.status} {response.url}")

        page.on("response", collect_response)
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

        containers = page.locator(".calendar .task-container")
        target = None
        for index in range(containers.count()):
            candidate = containers.nth(index)
            if candidate.locator(":scope > .calendar-task").count() == 0:
                target = candidate
                break
        require(target is not None, "an empty day is available for chapter and snap testing")

        palette = page.locator(".subjects-box .plan-lesson-palette:visible").first
        require(palette.count() == 1, "a lesson palette item is available")
        lesson_id = palette.get_attribute("data-lesson-id")
        require(bool(lesson_id), "palette lesson exposes its database id")

        drag_palette_to(page, palette, target, 245.0)
        task = target.locator(
            f':scope > .calendar-task[data-lesson-id="{lesson_id}"]'
        ).first
        require(task.count() == 1, "lesson was added to the calendar")
        page.wait_for_function(
            """
            element => Boolean(
              element &&
              element.querySelector('.task-chapter[data-plan-chapter-loader-version]')
            )
            """,
            arg=task.element_handle(),
            timeout=10_000,
        )

        student_id = page.locator("#student-select").input_value()
        chapter_response = context.request.get(
            urljoin(BASE_URL, "get-chapters/"),
            params={"student_id": student_id, "lesson_id": lesson_id},
        )
        require(chapter_response.status == 200, "chapter API accepts selected student and lesson")
        chapters = chapter_response.json()
        require(isinstance(chapters, list) and len(chapters) > 0, "chapter API returns real chapters")

        chapter_select = task.locator(".task-chapter")
        select2 = chapter_select.locator("xpath=following-sibling::*[contains(@class, 'select2-container')]").first
        require(select2.count() == 1, "chapter Select2 is initialized")
        select2.click()
        page.wait_for_function(
            """
            () => Array.from(document.querySelectorAll('.select2-results__option'))
              .some(option => !option.classList.contains('loading-results'))
            """,
            timeout=10_000,
        )
        option_texts = page.locator(".select2-results__option").all_inner_texts()
        require(
            any("فصل" in text or " - " in text for text in option_texts),
            "opening the chapter dropdown displays chapter options",
        )
        page.keyboard.press("Escape")

        drag_grid = task.evaluate(
            """
            element => {
              const instance = window.jQuery(element).draggable('instance');
              return instance && instance.options ? instance.options.grid : null;
            }
            """
        )
        require(
            bool(drag_grid and abs(float(drag_grid[1]) - GRID_PIXELS) <= 0.01),
            "calendar task drag is configured in exact 15-minute vertical steps",
        )

        title = task.locator(".task-title").first
        title_box = box(title)
        task_box_before = box(task)
        page.mouse.move(
            title_box["x"] + title_box["width"] / 2,
            title_box["y"] + title_box["height"] / 2,
        )
        page.mouse.down()
        page.mouse.move(
            title_box["x"] + title_box["width"] / 2 + 4,
            title_box["y"] + title_box["height"] / 2 + 4,
            steps=3,
        )
        page.mouse.move(
            title_box["x"] + title_box["width"] / 2,
            title_box["y"] + title_box["height"] / 2 + 24,
            steps=12,
        )
        page.wait_for_function(
            """
            () => {
              const badge = document.querySelector('.plan-quarter-feedback.is-visible');
              const line = document.querySelector('.plan-quarter-guide-line.is-visible');
              return Boolean(badge && line && badge.textContent.includes('۱۵ دقیقه'));
            }
            """,
            timeout=5_000,
        )
        require(
            page.locator(".plan-quarter-feedback.is-visible").count() == 1,
            "live start/end time feedback appears while dragging",
        )
        page.mouse.up()
        page.wait_for_timeout(350)

        task_top = task.evaluate("element => parseFloat(element.style.top || '0')")
        require(
            abs(task_top / GRID_PIXELS - round(task_top / GRID_PIXELS)) <= 0.01,
            "task finishes on a 15-minute grid boundary",
        )
        task_box_after = box(task)
        require(
            abs(task_box_after["y"] - task_box_before["y"]) >= GRID_PIXELS - 1,
            "real mouse movement advances the task by at least one visible step",
        )
        require(
            page.locator(".plan-quarter-feedback.is-visible").count() == 0,
            "drag feedback closes after mouse release",
        )

        require(not failed_requests, "chapter loading produced no failing requests: " + " | ".join(failed_requests))
        require(not page_errors, "chapter and snap flow has no uncaught JavaScript errors: " + " | ".join(page_errors))

        context.close()
        browser.close()

    print("Plan chapter loading and quarter-hour feedback regression completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
