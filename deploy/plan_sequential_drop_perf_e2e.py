from __future__ import annotations

import os
import sys
import time
from urllib.parse import urljoin

from playwright.sync_api import Locator, Page, sync_playwright


BASE_URL = os.environ.get(
    "PLAN_BASE_URL", "https://panel.kimiagarkhoone.com"
).rstrip("/") + "/"
USERNAME = os.environ.get("PLAN_USERNAME", "").strip()
PASSWORD = os.environ.get("PLAN_PASSWORD", "")
TEST_WEEK = os.environ.get("PLAN_TEST_WEEK", "1499-02-01")
STUDENT_LABEL = os.environ.get("PLAN_STUDENT_LABEL", "نمونه تجربی دوازدهم")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def drag_palette_to(page: Page, source: Locator, target: Locator, desired_top: float) -> None:
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
        steps=20,
    )
    page.mouse.up()


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
        "window.planRuntimeState && window.planRuntimeState.loaded && !window.planRuntimeState.loading",
        timeout=30_000,
    )
    page.wait_for_function(
        "window.planPerformanceGuard && window.planPerformanceGuard.stats.blockedIntervals >= 3",
        timeout=10_000,
    )


def clear_calendar(page: Page) -> None:
    page.evaluate(
        """
        () => window.jQuery('.calendar .calendar-task').remove()
        """
    )
    page.wait_for_timeout(100)


def main() -> int:
    if not USERNAME or not PASSWORD:
        print("PLAN_USERNAME and PLAN_PASSWORD are required.", file=sys.stderr)
        return 2

    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(locale="fa-IR", viewport={"width": 1700, "height": 1050})
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("dialog", lambda dialog: dialog.accept())

        page.goto(urljoin(BASE_URL, "login/"), wait_until="domcontentloaded", timeout=30_000)
        page.fill("#username", USERNAME)
        page.fill("#password", PASSWORD)
        page.click('form button[type="submit"]')
        page.wait_for_url("**/plan/", timeout=30_000)
        page.wait_for_function("window.jQuery && window.jQuery.ui", timeout=20_000)
        load_week(page)
        clear_calendar(page)

        palettes = page.locator(".subjects-box .plan-lesson-palette")
        require(palettes.count() >= 2, "at least two lesson palette items are available")
        first_palette = palettes.nth(0)
        second_palette = palettes.nth(1)
        first_id = first_palette.get_attribute("data-lesson-id")
        second_id = second_palette.get_attribute("data-lesson-id")
        require(bool(first_id and second_id and first_id != second_id), "two distinct lessons are available")

        containers = page.locator(".calendar .task-container")
        first_target = containers.nth(0)
        second_target = containers.nth(1)

        drag_palette_to(page, first_palette, first_target, 210)
        first_task = first_target.locator(
            f':scope > .calendar-task[data-lesson-id="{first_id}"]'
        ).first
        page.wait_for_function(
            "element => Boolean(element && element.querySelector('.task-chapter[data-plan-chapter-loader-version]'))",
            arg=first_task.element_handle(),
            timeout=10_000,
        )
        require(first_task.count() == 1, "first lesson is dropped")

        # Reproduce the real slow path: choose a chapter (and tests so the card
        # can compact), then immediately drop a different lesson.
        page.evaluate(
            """
            element => {
              const $task = window.jQuery(element);
              const $chapter = $task.find('.task-chapter');
              if (!$chapter.find('option[value="perf-chapter"]').length) {
                $chapter.append(new Option('فصل تست سرعت', 'perf-chapter', true, true));
              }
              $chapter.val('perf-chapter').trigger('change').trigger('select2:select');
              $task.find('.task-extra').val('20').trigger('change');
            }
            """,
            first_task.element_handle(),
        )
        page.wait_for_timeout(100)

        started = time.perf_counter()
        drag_palette_to(page, second_palette, second_target, 315)
        second_task = second_target.locator(
            f':scope > .calendar-task[data-lesson-id="{second_id}"]'
        ).first
        page.wait_for_function(
            "element => Boolean(element && element.isConnected)",
            arg=second_task.element_handle(),
            timeout=3_000,
        )
        elapsed = time.perf_counter() - started

        require(second_task.count() == 1, "second lesson appears after chapter selection")
        require(
            elapsed < 2.5,
            f"second lesson drop stays responsive ({elapsed:.2f}s < 2.5s)",
        )
        require(
            not errors,
            "sequential lesson flow has no uncaught JavaScript errors: " + " | ".join(errors),
        )

        stats = page.evaluate("() => window.planPerformanceGuard.stats")
        print(
            "Performance guard stats: "
            f"blockedIntervals={stats['blockedIntervals']}, "
            f"filteredMutationBatches={stats['filteredMutationBatches']}"
        )

        context.close()
        browser.close()

    print("Sequential Plan drop performance regression completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
