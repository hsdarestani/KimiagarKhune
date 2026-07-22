from __future__ import annotations

import json
import os
import sys
from urllib.parse import urljoin

from playwright.sync_api import Locator, Page, sync_playwright


BASE_URL = os.environ.get(
    "PLAN_BASE_URL", "https://panel.kimiagarkhoone.com"
).rstrip("/") + "/"
USERNAME = os.environ.get("PLAN_USERNAME", "").strip()
PASSWORD = os.environ.get("PLAN_PASSWORD", "")
TEST_WEEK = os.environ.get("PLAN_SCHOOL_TEST_WEEK", "1499-03-01")
STUDENT_LABEL = os.environ.get(
    "PLAN_STUDENT_LABEL", "نمونه تجربی دوازدهم"
)
GRID_PIXELS = 8.75


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def info(label: str, value) -> None:
    print(f"INFO: {label}={json.dumps(value, ensure_ascii=False, default=str)}")


def relative_top(task: Locator, container: Locator) -> float:
    task_box = task.bounding_box()
    container_box = container.bounding_box()
    if not task_box or not container_box:
        raise AssertionError("Could not read task/container position")
    return task_box["y"] - container_box["y"]


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
        "document.querySelector('script[data-plan-drag-surface=true]')",
        timeout=15_000,
    )

    asset_info = page.evaluate(
        """
        async () => {
          const script = document.querySelector('script[data-plan-drag-surface=true]');
          let source = '';
          let fetchError = '';
          try {
            source = await fetch(script.src, {cache: 'no-store'}).then(response => response.text());
          } catch (error) {
            fetchError = String(error);
          }
          return {
            src: script ? script.src : '',
            captureBound: window.__planDragSurfaceCaptureBound === true,
            hasNativeCaptureSource: source.includes('__planDragSurfaceCaptureBound'),
            hasLifecycleWrapperSource: source.includes('planDragSurfaceWrapped'),
            fetchError,
            readyState: document.readyState,
            jqueryUi: Boolean(window.jQuery && window.jQuery.ui)
          };
        }
        """
    )
    info("drag_surface_asset", asset_info)


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
    page.wait_for_timeout(300)


def drag_task_via_school(
    page: Page,
    task: Locator,
    target: Locator,
    desired_top: float,
    *,
    school_waypoint_top: float = 140,
) -> None:
    task_box = task.bounding_box()
    title = task.locator(".task-title").first
    title_box = title.bounding_box()
    target_box = target.bounding_box()
    if not task_box or not title_box or not target_box:
        raise AssertionError("Task title or target is not visible")

    start_x = title_box["x"] + title_box["width"] / 2
    start_y = title_box["y"] + title_box["height"] / 2
    grab_offset = start_y - task_box["y"]
    target_x = target_box["x"] + target_box["width"] / 2

    hit_info = page.evaluate(
        """
        ({x, y}) => {
          const hit = document.elementFromPoint(x, y);
          const task = hit ? hit.closest('.calendar-task') : null;
          const cancel = hit ? hit.closest(
            'button, input, textarea, select, option, .select2-container, .plan-resize-handle, .plan-study-compact'
          ) : null;
          return {
            x,
            y,
            hitTag: hit ? hit.tagName : null,
            hitClass: hit ? hit.className : null,
            hitText: hit ? String(hit.textContent || '').trim().slice(0, 80) : null,
            closestTaskType: task ? task.dataset.boxType : null,
            closestTaskClass: task ? task.className : null,
            cancelTag: cancel ? cancel.tagName : null,
            cancelClass: cancel ? cancel.className : null
          };
        }
        """,
        {"x": start_x, "y": start_y},
    )
    info("study_drag_hit", hit_info)

    widget_info = task.evaluate(
        """
        element => {
          const $element = window.jQuery(element);
          let instance = null;
          try { instance = $element.draggable('instance'); } catch (_) {}
          const start = instance && instance.options ? instance.options.start : null;
          const stop = instance && instance.options ? instance.options.stop : null;
          const title = element.querySelector('.task-title');
          return {
            taskClass: element.className,
            taskVersion: element.dataset.planInteractionVersion || '',
            uiDraggable: Boolean(instance),
            disabled: Boolean(instance && instance.options && instance.options.disabled),
            cancel: instance && instance.options ? instance.options.cancel : null,
            distance: instance && instance.options ? instance.options.distance : null,
            startWrapped: Boolean(start && start.planDragSurfaceWrapped),
            stopWrapped: Boolean(stop && stop.planDragSurfaceWrapped),
            titlePointerEvents: title ? getComputedStyle(title).pointerEvents : null,
            titlePosition: title ? getComputedStyle(title).position : null
          };
        }
        """
    )
    info("study_drag_widget", widget_info)

    page.mouse.move(start_x, start_y)
    page.mouse.down()
    down_state = page.evaluate(
        """
        () => ({
          active: document.body.classList.contains('plan-calendar-drag-active'),
          activeSources: document.querySelectorAll('.plan-active-drag-source').length
        })
        """
    )
    info("after_mouse_down", down_state)

    page.mouse.move(start_x + 6, start_y + 6, steps=3)
    move_state = page.evaluate(
        """
        () => ({
          active: document.body.classList.contains('plan-calendar-drag-active'),
          activeSources: document.querySelectorAll('.plan-active-drag-source').length,
          ghosts: document.querySelectorAll('.plan-drag-ghost').length,
          draggingSources: document.querySelectorAll('.plan-dragging-source').length
        })
        """
    )
    info("after_initial_move", move_state)

    page.mouse.move(
        start_x,
        target_box["y"] + school_waypoint_top + grab_offset,
        steps=16,
    )
    page.mouse.move(
        target_x,
        target_box["y"] + school_waypoint_top + grab_offset,
        steps=20,
    )
    page.mouse.move(
        target_x,
        target_box["y"] + desired_top + grab_offset,
        steps=20,
    )
    page.mouse.up()
    page.wait_for_timeout(350)


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
            viewport={"width": 1700, "height": 1100},
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
        load_test_week(page)

        school_count = page.evaluate(
            """
            () => Array.from(document.querySelectorAll('.calendar-task')).filter(task => {
              const title = task.querySelector('.task-title');
              return title && String(title.value || title.textContent || '').trim() === 'مدرسه';
            }).length
            """
        )
        require(school_count >= 5, "five default school blocks remain visible")
        require(
            not any("برنامه آینده" in message for message in dialogs),
            "demo student is not blocked by a synthetic far-future report",
        )

        containers = page.locator(".calendar .task-container")
        first = containers.nth(0)
        second = containers.nth(1)
        lesson_palette = page.locator(
            ".subjects-box .plan-lesson-palette"
        ).first

        drag_palette_to(page, lesson_palette, first, 525)
        study = first.locator(
            '.calendar-task[data-box-type="مطالعه"]'
        ).first
        require(study.count() == 1, "study box is created below school hours")

        drag_task_via_school(page, study, second, 560)
        moved_study = second.locator(
            '.calendar-task[data-box-type="مطالعه"]'
        ).first
        require(
            moved_study.count() == 1,
            "study box moves to another day while school blocks exist",
        )
        require(
            abs(relative_top(moved_study, second) - 560) <= GRID_PIXELS + 2,
            "school blocks do not corrupt the intended evening drop time",
        )
        require(
            not page.locator("body").evaluate(
                "body => body.classList.contains('plan-calendar-drag-active')"
            ),
            "drag surface mode is cleared after mouse release",
        )

        original_top = relative_top(moved_study, second)
        drag_task_via_school(
            page,
            moved_study,
            first,
            105,
            school_waypoint_top=150,
        )
        require(
            second.locator('.calendar-task[data-box-type="مطالعه"]').count() == 1
            and abs(relative_top(moved_study, second) - original_top)
            <= GRID_PIXELS + 2,
            "school time still rejects overlap and restores the previous position",
        )

        require(
            not page_errors,
            "school-block drag produces no uncaught JavaScript errors: "
            + " | ".join(page_errors),
        )
        context.close()
        browser.close()

    print("School-block Plan drag regression completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
