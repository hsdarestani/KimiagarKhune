from __future__ import annotations

import os
import sys
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


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


def load_week(page) -> None:
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
        "window.planPersistenceFixes && window.planPersistenceFixes.version === '2026.08.18.1'",
        timeout=15_000,
    )


def main() -> int:
    if not USERNAME or not PASSWORD:
        print("PLAN_USERNAME and PLAN_PASSWORD are required.", file=sys.stderr)
        return 2

    page_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(locale="fa-IR", viewport={"width": 1700, "height": 1050})
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("dialog", lambda dialog: dialog.accept())

        page.goto(urljoin(BASE_URL, "login/"), wait_until="domcontentloaded", timeout=30_000)
        page.fill("#username", USERNAME)
        page.fill("#password", PASSWORD)
        page.click('form button[type="submit"]')
        page.wait_for_url("**/plan/", timeout=30_000)
        page.wait_for_function("window.jQuery && window.jQuery.ui", timeout=20_000)
        load_week(page)

        export_result = page.evaluate(
            """
            () => {
              const $ = window.jQuery;
              const $container = $('.calendar .task-container').first();
              const makeEditable = (type, value, top) => {
                const $task = $('<div class="calendar-task"></div>')
                  .attr('data-box-type', type)
                  .css({position: 'absolute', top: top + 'px', height: '35px', left: '5%'});
                const $input = $('<input type="text" class="task-title task-inp editable">');
                // Reproduce the actual browser problem: update the live property
                // without updating the serialized HTML value attribute.
                $input[0].value = value;
                $task.append($input).append('<div class="time-label"></div>');
                $container.append($task);
                return $input[0];
              };

              const eventInput = makeEditable('ایونت', 'کلاس فیزیک یازدهم خروجی', 420);
              const assignmentInput = makeEditable(
                'تکلیف',
                'آمادگی و تکلیف کلاس فیزیک یازدهم خروجی',
                472.5
              );
              const before = {
                eventAttr: eventInput.getAttribute('value'),
                assignmentAttr: assignmentInput.getAttribute('value')
              };

              window.planPersistenceFixes.synchronizeTitlesForExport();
              const html = $('.calendar-wrapper').clone().prop('outerHTML');
              return {
                before,
                eventAttr: eventInput.getAttribute('value'),
                assignmentAttr: assignmentInput.getAttribute('value'),
                containsEvent: html.includes('کلاس فیزیک یازدهم خروجی'),
                containsAssignment: html.includes('آمادگی و تکلیف کلاس فیزیک یازدهم خروجی')
              };
            }
            """
        )
        require(
            export_result["before"]["eventAttr"] in (None, ""),
            "test reproduces a live event title that was absent from serialized HTML",
        )
        require(
            export_result["eventAttr"] == "کلاس فیزیک یازدهم خروجی",
            "event title is synchronized before PDF cloning",
        )
        require(
            export_result["assignmentAttr"] == "آمادگی و تکلیف کلاس فیزیک یازدهم خروجی",
            "event-derived assignment title is synchronized before PDF cloning",
        )
        require(
            export_result["containsEvent"] and export_result["containsAssignment"],
            "serialized PDF calendar clone contains both visible titles",
        )

        recurring_result = page.evaluate(
            """
            async () => {
              const $ = window.jQuery;
              const state = window.planRuntimeState;
              const defaults = await $.getJSON('/get_default_events/', {
                student_id: state.studentId
              });

              $('.calendar .calendar-task').remove();
              const $first = $('.calendar .task-container').first();
              const $saved = $('<div class="calendar-task event-task"></div>')
                .attr('data-box-type', 'ایونت')
                .css({position: 'absolute', top: '560px', height: '35px', left: '5%'})
                .append('<input type="text" class="task-title task-inp editable" value="رویداد ذخیره‌شده غیرتکراری">')
                .append('<div class="time-label"></div>');
              $first.append($saved);

              const added = window.planPersistenceFixes.mergeRecurringEvents(defaults);
              const recurring = $('.calendar .calendar-task[data-recurring-default="true"]');
              const savedStillVisible = $('.calendar .calendar-task .task-title').filter(function () {
                return String($(this).val() || $(this).text() || '').trim() === 'رویداد ذخیره‌شده غیرتکراری';
              }).length > 0;
              return {
                defaults: defaults.length,
                added,
                recurring: recurring.length,
                savedStillVisible
              };
            }
            """
        )
        require(recurring_result["defaults"] > 0, "student has recurring default events")
        require(
            recurring_result["added"] > 0 and recurring_result["recurring"] > 0,
            "recurring classes are merged even when another saved task already exists",
        )
        require(
            recurring_result["savedStillVisible"],
            "merging recurring classes preserves the saved weekly task",
        )
        require(
            not page_errors,
            "persistence flow has no uncaught JavaScript errors: " + " | ".join(page_errors),
        )

        context.close()
        browser.close()

    print("Plan persistence regression completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
