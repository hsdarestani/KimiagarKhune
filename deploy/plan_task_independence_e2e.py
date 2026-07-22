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
TEST_WEEK = os.environ.get("PLAN_GEOMETRY_TEST_WEEK", "1405-09-01")
STUDENT_LABEL = os.environ.get(
    "PLAN_GEOMETRY_STUDENT_LABEL", "نمونه ریاضی یازدهم"
)


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
        source_box["x"] + source_box["width"] / 2 + 8,
        source_box["y"] + source_box["height"] / 2 + 8,
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
        "window.planTaskGeometry && "
        "document.body.dataset.planTaskGeometryVersion",
        timeout=15_000,
    )
    page.wait_for_timeout(250)


def main() -> int:
    if not USERNAME or not PASSWORD:
        print("PLAN_USERNAME and PLAN_PASSWORD are required.", file=sys.stderr)
        return 2

    page_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            locale="fa-IR",
            viewport={"width": 1800, "height": 1050},
        )
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("dialog", lambda dialog: dialog.accept())

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
        require(target is not None, "an empty day column is available")

        palette = page.locator(".subjects-box .plan-lesson-palette:visible")
        require(palette.count() >= 2, "two visible lesson cards are available")

        first_source = palette.nth(0)
        second_source = palette.nth(1)
        first_id = first_source.get_attribute("data-lesson-id")
        second_id = second_source.get_attribute("data-lesson-id")
        require(bool(first_id and second_id), "lesson cards expose stable lesson ids")

        drag_palette_to(page, first_source, target, 175)
        drag_palette_to(page, second_source, target, 420)

        first = target.locator(
            f':scope > .calendar-task[data-lesson-id="{first_id}"]'
        ).first
        second = target.locator(
            f':scope > .calendar-task[data-lesson-id="{second_id}"]'
        ).first
        require(first.count() == 1 and second.count() == 1, "two study tasks were added to one day")

        positions = page.evaluate(
            """
            ([first, second]) => ({
              first: getComputedStyle(first).position,
              second: getComputedStyle(second).position,
              firstTop: first.getBoundingClientRect().top,
              secondTop: second.getBoundingClientRect().top,
              firstHeight: first.getBoundingClientRect().height,
              secondCssTop: parseFloat(second.style.top || '0')
            })
            """,
            [first.element_handle(), second.element_handle()],
        )
        require(positions["first"] == "absolute", "first new task is absolutely positioned")
        require(positions["second"] == "absolute", "second new task is absolutely positioned")

        second_before_resize = box(second)["y"]
        second_css_top_before = page.evaluate(
            "element => parseFloat(element.style.top || '0')", second.element_handle()
        )
        first_height_before = box(first)["height"]

        handle = first.locator(":scope > .plan-resize-handle")
        require(handle.count() == 1, "first task has a resize handle")
        handle_box = box(handle)
        page.mouse.move(
            handle_box["x"] + handle_box["width"] / 2,
            handle_box["y"] + handle_box["height"] / 2,
        )
        page.mouse.down()
        page.mouse.move(
            handle_box["x"] + handle_box["width"] / 2,
            handle_box["y"] + handle_box["height"] / 2 + 70,
            steps=20,
        )
        page.mouse.up()
        page.wait_for_timeout(350)

        first_height_after = box(first)["height"]
        second_after_resize = box(second)["y"]
        second_css_top_after = page.evaluate(
            "element => parseFloat(element.style.top || '0')", second.element_handle()
        )
        require(
            first_height_after >= first_height_before + 50,
            "resizing the first task changes its own height",
        )
        require(
            abs(second_after_resize - second_before_resize) <= 1.0,
            "resizing the first task does not move the second task",
        )
        require(
            abs(second_css_top_after - second_css_top_before) <= 0.1,
            "resizing the first task does not alter the second task top state",
        )

        second_before_delete = box(second)["y"]
        first.locator(":scope > .remove-btn").click()
        page.wait_for_timeout(250)
        require(first.count() == 0, "first task was removed")
        second_after_delete = box(second)["y"]
        require(
            abs(second_after_delete - second_before_delete) <= 1.0,
            "deleting the first task does not move the second task",
        )
        require(
            page.evaluate(
                "element => getComputedStyle(element).position", second.element_handle()
            )
            == "absolute",
            "remaining task stays absolutely positioned after sibling deletion",
        )

        require(
            not page_errors,
            "same-day task independence has no uncaught JavaScript errors: "
            + " | ".join(page_errors),
        )

        context.close()
        browser.close()

    print("Plan task independence regression completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
