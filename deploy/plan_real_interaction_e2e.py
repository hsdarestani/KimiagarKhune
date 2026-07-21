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
TEST_WEEK = os.environ.get("PLAN_TEST_WEEK", "1499-02-01")
STUDENT_LABEL = os.environ.get(
    "PLAN_STUDENT_LABEL", "نمونه تجربی دوازدهم"
)
GRID_PIXELS = 8.75


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def relative_top(task: Locator, container: Locator) -> float:
    task_box = task.bounding_box()
    container_box = container.bounding_box()
    if not task_box or not container_box:
        raise AssertionError("Could not read task/container position")
    return task_box["y"] - container_box["y"]


def drag_palette_to(
    page: Page,
    source: Locator,
    target: Locator,
    desired_top: float,
) -> None:
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
        source_box["x"] + source_box["width"] / 2 + 5,
        source_box["y"] + source_box["height"] / 2 + 5,
        steps=3,
    )
    page.mouse.move(
        target_box["x"] + target_box["width"] / 2,
        target_box["y"] + desired_top,
        steps=24,
    )
    page.mouse.up()
    page.wait_for_timeout(250)


def drag_task_to(
    page: Page,
    task: Locator,
    target: Locator,
    desired_top: float,
    grab_offset: float = 14,
) -> None:
    task_box = task.bounding_box()
    target_box = target.bounding_box()
    if not task_box or not target_box:
        raise AssertionError("Task or target is not visible")

    page.mouse.move(
        task_box["x"] + task_box["width"] / 2,
        task_box["y"] + grab_offset,
    )
    page.mouse.down()
    page.mouse.move(
        task_box["x"] + task_box["width"] / 2 + 6,
        task_box["y"] + grab_offset + 6,
        steps=3,
    )
    page.mouse.move(
        target_box["x"] + target_box["width"] / 2,
        target_box["y"] + desired_top + grab_offset,
        steps=28,
    )
    page.mouse.up()
    page.wait_for_timeout(300)


def resize_from_bottom(page: Page, task: Locator, delta_y: float) -> None:
    handle = task.locator(".plan-resize-handle")
    handle_box = handle.bounding_box()
    if not handle_box:
        raise AssertionError("Resize handle is not visible")

    x = handle_box["x"] + handle_box["width"] / 2
    y = handle_box["y"] + handle_box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x, y + delta_y, steps=24)
    page.mouse.up()
    page.wait_for_timeout(250)


def clear_calendar(page: Page) -> None:
    page.evaluate(
        """
        () => {
          window.jQuery('.calendar-task').each(function () {
            const $task = window.jQuery(this);
            try { if ($task.draggable('instance')) $task.draggable('destroy'); } catch (_) {}
            try { if ($task.resizable('instance')) $task.resizable('destroy'); } catch (_) {}
            $task.remove();
          });
        }
        """
    )


def load_test_week(page: Page) -> None:
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
        "window.planRuntimeState && "
        "window.planRuntimeState.loaded && "
        "!window.planRuntimeState.loading",
        timeout=30_000,
    )
    page.wait_for_function(
        "document.querySelectorAll('.calendar .task-container.ui-droppable').length === 7",
        timeout=15_000,
    )
    page.wait_for_function(
        "document.querySelector('script[data-plan-interactions=true]')",
        timeout=15_000,
    )


def main() -> int:
    if not USERNAME or not PASSWORD:
        print("PLAN_USERNAME and PLAN_PASSWORD are required.", file=sys.stderr)
        return 2

    page_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            locale="fa-IR",
            viewport={"width": 1700, "height": 1100},
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
        load_test_week(page)
        clear_calendar(page)

        containers = page.locator(".calendar .task-container")
        first = containers.nth(0)
        second = containers.nth(1)

        event_palette = page.locator(
            '.events-box .plan-event-palette[data-kind="event"]'
        ).first
        drag_palette_to(page, event_palette, first, 87.5)

        event = first.locator(
            '.calendar-task[data-box-type="ایونت"]'
        ).first
        require(event.count() == 1, "real mouse drop creates an event")
        require(
            abs(relative_top(event, first) - 87.5) <= GRID_PIXELS + 2,
            "palette drop lands on the intended 15-minute slot",
        )
        require(
            event.locator(".plan-resize-handle").count() == 1,
            "event exposes a visible bottom resize handle",
        )

        drag_task_to(page, event, first, 192.5)
        require(
            abs(relative_top(event, first) - 192.5) <= GRID_PIXELS + 2,
            "an existing box moves accurately inside the same day",
        )

        drag_task_to(page, event, second, 122.5)
        moved_event = second.locator(
            '.calendar-task[data-box-type="ایونت"]'
        ).first
        require(moved_event.count() == 1, "an existing box moves to another day")
        require(
            abs(relative_top(moved_event, second) - 122.5) <= GRID_PIXELS + 2,
            "cross-day move preserves the intended time slot",
        )

        old_height = moved_event.bounding_box()["height"]
        old_label = moved_event.locator(".time-label").inner_text().strip()
        resize_from_bottom(page, moved_event, 70)
        new_height = moved_event.bounding_box()["height"]
        new_label = moved_event.locator(".time-label").inner_text().strip()
        require(
            new_height >= old_height + 60,
            "dragging the bottom handle increases box duration",
        )
        require(new_label != old_label, "resize updates the displayed end time live")

        lesson_palette = page.locator(
            ".subjects-box .plan-lesson-palette"
        ).first
        drag_palette_to(page, lesson_palette, first, 315)
        study = first.locator(
            '.calendar-task[data-box-type="مطالعه"]'
        ).first
        require(study.count() == 1, "real mouse drop creates a study box")

        page.evaluate(
            """
            () => {
              const $task = window.jQuery('.calendar-task[data-box-type="مطالعه"]').first();
              const $chapter = $task.find('.task-chapter');
              if (!$chapter.find('option[value="e2e-chapter"]').length) {
                $chapter.append(new Option('فصل آزمایشی', 'e2e-chapter', true, true));
              }
              $chapter.val('e2e-chapter').trigger('change');
              $task.find('.task-extra').val('20').trigger('change');
            }
            """
        )
        page.wait_for_timeout(250)
        require(
            study.locator(".plan-study-compact:visible").count() == 1,
            "chapter and test dropdowns collapse after both selections",
        )
        require(
            study.locator(".plan-study-edit:visible").count() == 1,
            "collapsed study controls show the pencil edit button",
        )
        require(
            study.locator(".select2-container:visible").count() == 0,
            "large Select2 controls are hidden in compact mode",
        )

        study.locator(".plan-study-edit").click()
        page.wait_for_timeout(100)
        require(
            study.locator(".select2-container:visible").count() >= 2,
            "pencil button restores chapter and test dropdowns",
        )

        original_top = relative_top(moved_event, second)
        drag_task_to(page, moved_event, first, 315)
        require(
            moved_event.locator("xpath=ancestor::*[contains(@class,'day-column')]").count() == 1
            and abs(relative_top(moved_event, second) - original_top) <= GRID_PIXELS + 2,
            "overlap rejection returns a box to its previous day and time",
        )

        require(
            not page_errors,
            "real interactions produce no uncaught JavaScript errors: "
            + " | ".join(page_errors),
        )
        context.close()
        browser.close()

    print("Real Plan interaction regression completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
