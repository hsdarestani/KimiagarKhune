from __future__ import annotations

import os
import sys
from urllib.parse import urljoin

from playwright.sync_api import Page, sync_playwright


BASE_URL = os.environ.get("PLAN_BASE_URL", "https://panel.kimiagarkhoone.com").rstrip("/") + "/"
USERNAME = os.environ.get("PLAN_USERNAME", "").strip()
PASSWORD = os.environ.get("PLAN_PASSWORD", "")
TEST_WEEK = os.environ.get("PLAN_TEST_WEEK", "1499-01-01")
STUDENT_LABEL = os.environ.get("PLAN_STUDENT_LABEL", "نمونه تجربی دوازدهم")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def drop_palette(page: Page, source_selector: str, day_index: int, top_pixels: int) -> None:
    result = page.evaluate(
        """
        ({sourceSelector, dayIndex, topPixels}) => {
          const $source = window.jQuery(sourceSelector).first();
          const $target = window.jQuery('.calendar .day-column').eq(dayIndex).find('.task-container');
          if (!$source.length || !$target.length || !$target.hasClass('ui-droppable')) {
            return {ok: false, source: $source.length, target: $target.length};
          }
          const callback = $target.droppable('option', 'drop');
          const offset = $target.offset();
          callback.call(
            $target[0],
            window.jQuery.Event('drop', {pageY: offset.top + topPixels}),
            {
              draggable: $source,
              offset: {top: offset.top + topPixels, left: offset.left + 10}
            }
          );
          return {ok: true};
        }
        """,
        {
            "sourceSelector": source_selector,
            "dayIndex": day_index,
            "topPixels": top_pixels,
        },
    )
    require(bool(result.get("ok")), f"drop source {source_selector} into day {day_index}")


def clear_calendar(page: Page) -> None:
    page.evaluate(
        """
        () => {
          window.jQuery('.calendar-task').each(function () {
            const $task = window.jQuery(this);
            if ($task.hasClass('ui-draggable')) $task.draggable('destroy');
            if ($task.hasClass('ui-resizable')) $task.resizable('destroy');
            $task.find('select.select2-hidden-accessible').each(function () {
              try { window.jQuery(this).select2('destroy'); } catch (_) {}
            });
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
          const $input = window.jQuery('#weekSelector');
          $input.val(value).trigger('input').trigger('change');
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
        "window.jQuery('.calendar .task-container.ui-droppable').length === 7",
        timeout=10_000,
    )


def main() -> int:
    if not USERNAME or not PASSWORD:
        print("PLAN_USERNAME and PLAN_PASSWORD are required.", file=sys.stderr)
        return 2

    page_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(locale="fa-IR", viewport={"width": 1600, "height": 1000})
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("dialog", lambda dialog: dialog.accept())

        page.goto(urljoin(BASE_URL, "login/"), wait_until="domcontentloaded", timeout=30_000)
        page.fill("#username", USERNAME)
        page.fill("#password", PASSWORD)
        page.click('form button[type="submit"]')
        page.wait_for_url("**/plan/", timeout=30_000)
        page.wait_for_function("window.jQuery && window.jQuery.ui", timeout=20_000)
        page.wait_for_function("window.planRuntimeState", timeout=20_000)

        require(page.locator('script[data-plan-runtime="true"]').count() == 1, "runtime is loaded exactly once")
        require(page.locator(".calendar .day-column").count() == 7, "seven calendar day columns exist")

        load_test_week(page)
        require(page.locator(".calendar .task-container.ui-droppable").count() == 7, "all days accept drops")
        clear_calendar(page)

        drop_palette(page, '.events-box .plan-event-palette[data-kind="event"]', 0, 70)
        event = page.locator('.calendar .day-column').nth(0).locator('.calendar-task[data-box-type="ایونت"]').first
        require(event.count() == 1, "event box is created")
        require("ui-draggable" in (event.get_attribute("class") or ""), "event is draggable")
        require("ui-resizable" in (event.get_attribute("class") or ""), "event is resizable")
        require(event.locator(".time-label").inner_text().strip() == "08:00 - 09:30", "drop time is calculated from position")

        event.locator(".task-title").fill("جلسه E2E")
        page.evaluate(
            """
            () => {
              const $task = window.jQuery('.calendar .day-column').eq(0).find('.calendar-task[data-box-type="ایونت"]').first();
              const stop = $task.resizable('option', 'stop');
              $task.css('height', '70px');
              stop.call($task[0], window.jQuery.Event('resizestop'), {size: {height: 70}});
            }
            """
        )
        require(event.locator(".time-label").inner_text().strip() == "08:00 - 10:00", "resize updates the end time")

        event.locator(".tick-btn").click()
        require(page.locator(".assignments-box .plan-assignment-palette").count() == 1, "event creates an assignment palette item")
        drop_palette(page, ".assignments-box .plan-assignment-palette", 1, 140)
        require(
            page.locator('.calendar .day-column').nth(1).locator('.calendar-task[data-box-type="تکلیف"]').count() == 1,
            "assignment is dropped into another day",
        )

        drop_palette(page, '.events-box .plan-event-palette[data-kind="floating"]', 2, 70)
        require(
            page.locator('.calendar .day-column').nth(2).locator('.calendar-task[data-box-type="شناور"].floating').count() == 1,
            "floating box keeps its own type and style",
        )

        page.check("#examWeekCheckbox")
        require(page.locator(".events-box .exam-task").count() == 4, "exam week exposes four exam templates")
        drop_palette(page, ".events-box .exam-task", 3, 70)
        exam = page.locator('.calendar .day-column').nth(3).locator('.calendar-task[data-box-type="ایونت"]').first
        require(exam.count() == 1, "exam template creates an event")
        require(exam.evaluate("element => parseFloat(element.style.height) >= 120"), "exam duration controls box height")

        lesson_count = page.locator(".subjects-box .plan-lesson-palette").count()
        require(lesson_count > 0, "student lessons are loaded")
        drop_palette(page, ".subjects-box .plan-lesson-palette", 4, 70)
        study = page.locator('.calendar .day-column').nth(4).locator('.calendar-task[data-box-type="مطالعه"].extended-task').first
        require(study.count() == 1, "lesson creates an extended study box")
        require(study.get_attribute("data-lesson-id") is not None, "study box keeps lesson id")
        require(study.locator(".task-chapter").count() == 1, "study box has chapter selector")
        require(study.locator(".task-extra").count() == 1, "study box has test-count selector")

        before_repeat = page.locator('.calendar-task[data-box-type="مطالعه"]').count()
        study.locator(".repeat-btn").click()
        after_repeat = page.locator('.calendar-task[data-box-type="مطالعه"]').count()
        require(after_repeat > before_repeat, "repeat copies study boxes to free days")

        second_day = page.locator(".calendar .day-column").nth(1)
        before_rest = second_day.locator(".calendar-task").count()
        second_day.locator(".disable-day-checkbox").check()
        require(second_day.locator(".calendar-task").count() == 0, "rest day temporarily removes its boxes")
        second_day.locator(".disable-day-checkbox").uncheck()
        require(second_day.locator(".calendar-task").count() == before_rest, "rest day restores its boxes")

        first_day = page.locator(".calendar .day-column").nth(0)
        before_holiday = first_day.locator('.calendar-task[data-box-type="ایونت"]').count()
        first_day.locator(".remove-events-checkbox").check()
        require(first_day.locator('.calendar-task[data-box-type="ایونت"]').count() == 0, "holiday hides event boxes")
        first_day.locator(".remove-events-checkbox").uncheck()
        require(first_day.locator('.calendar-task[data-box-type="ایونت"]').count() == before_holiday, "holiday restores event boxes")

        removable = page.locator('.calendar-task[data-box-type="مطالعه"]').last
        total_before_remove = page.locator(".calendar-task").count()
        removable.locator(".remove-btn").click()
        require(page.locator(".calendar-task").count() == total_before_remove - 1, "remove button deletes one box")

        with page.expect_response(lambda response: response.url.endswith("/save-weekly-report/") and response.request.method == "POST", timeout=30_000) as save_info:
            page.click(".save-btn")
        save_response = save_info.value
        require(save_response.ok, "save API returns success")
        save_payload = save_response.json()
        require(save_payload.get("status") == "success", "save response reports success")

        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("window.planRuntimeState", timeout=20_000)
        load_test_week(page)
        saved_types = set(
            page.locator(".calendar-task").evaluate_all(
                "elements => elements.map(element => element.dataset.boxType)"
            )
        )
        require({"ایونت", "تکلیف", "شناور", "مطالعه"}.issubset(saved_types), "all box types survive save and reload")
        require(page.locator(".calendar-task.ui-draggable.ui-resizable").count() == page.locator(".calendar-task").count(), "reloaded boxes remain draggable and resizable")

        require(not page_errors, "browser produced no uncaught JavaScript errors: " + " | ".join(page_errors))
        context.close()
        browser.close()

    print("Plan browser regression completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
