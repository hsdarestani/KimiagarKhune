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
    page.wait_for_function(
        "window.planOutputPolish && window.planOutputPolish.version === '2026.08.19.1'",
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

        filename_result = page.evaluate(
            """
            () => ({
              fileName: window.planOutputPolish.studentPdfFileName(''),
              summaryName: window.planOutputPolish.studentPdfFileName('خلاصه'),
              rewritten: window.planOutputPolish.rewritePdfMarkup(
                '<html><head><title>خروجی هفته</title></head><body><script>pdf.save("generic.pdf");<\\/script></body></html>',
                window.planOutputPolish.studentPdfFileName(''),
                window.jQuery('#student-select option:selected').text().trim()
              )
            })
            """
        )
        require(
            filename_result["fileName"] == f"{STUDENT_LABEL}.pdf",
            "weekly PDF filename is the selected student's name",
        )
        require(
            filename_result["summaryName"] == f"{STUDENT_LABEL}-خلاصه.pdf",
            "summary PDF filename keeps the selected student's name",
        )
        require(
            filename_result["fileName"] in filename_result["rewritten"],
            "popup PDF save markup is rewritten to the student filename",
        )

        visual_result = page.evaluate(
            """
            () => {
              const $ = window.jQuery;
              const $container = $('.calendar .task-container').first();

              const $study = $('<div class="calendar-task extended-task"></div>')
                .attr('data-box-type', 'مطالعه')
                .attr('data-lesson-id', '999991')
                .attr('data-lesson-name', 'زیست')
                .css({position: 'absolute', top: '620px', height: '70px', left: '5%', backgroundColor: 'rgb(123, 190, 94)'})
                .append('<div class="task-title">زیست دهم</div>')
                .append('<select class="task-chapter"><option value="1" selected>فصل ۳ - تبادلات</option></select>')
                .append('<span class="select2-container" style="display:block;width:28px;height:58px;border:1px solid #111"></span>')
                .append('<select class="task-extra"><option value="45" selected>45</option></select>')
                .append('<div class="ui-resizable-handle ui-resizable-s" style="display:block;width:22px;height:54px;border:1px solid #222"></div>')
                .append('<div class="time-label"></div>');
              $container.append($study);

              const cleanup = window.planOutputPolish.prepareExportUi();
              const $clone = $('.calendar-wrapper').clone();
              const hiddenArtifacts = $clone.find('[data-plan-export-hidden="true"]');
              const artifactsStillDisplayed = hiddenArtifacts.filter(function () {
                return String($(this).attr('style') || '').indexOf('display: none') === -1;
              }).length;
              const mirrorText = $clone.find('.plan-export-study-meta').last().text();
              cleanup();

              const $source = $('<div class="calendar-task extended-task"></div>')
                .attr('data-box-type', 'مطالعه')
                .attr('data-lesson-id', '999992')
                .attr('data-lesson-name', 'زیست')
                .css({position: 'absolute', top: '710px', height: '52.5px', left: '5%', backgroundColor: 'rgb(154, 205, 50)'})
                .append('<button type="button" class="repeat-btn">تکرار</button>')
                .append('<div class="task-title">زیست دهم</div>');
              const $repeated = $('<div class="calendar-task extended-task"></div>')
                .attr('data-box-type', 'مطالعه')
                .attr('data-lesson-id', '999992')
                .css({position: 'absolute', top: '710px', height: '52.5px', left: '5%', backgroundColor: 'rgb(227, 242, 253)'})
                .append('<div class="task-title">زیست دهم</div>');
              $container.append($source).append($repeated);
              window.planOutputPolish.preserveRepeatedStudyColor($source.find('.repeat-btn')[0]);
              const sourceColor = getComputedStyle($source[0]).backgroundColor;
              const repeatedColor = getComputedStyle($repeated[0]).backgroundColor;

              const longTitle = 'آمادگی و تکلیف مشاهده کلاس شیمی و مرور نکات جلسه قبل';
              const $assignment = $('<div class="calendar-task"></div>')
                .attr('data-box-type', 'تکلیف')
                .css({position: 'absolute', top: '790px', height: '52.5px', left: '5%'})
                .append($('<input type="text" class="task-title task-inp editable">').val(longTitle))
                .append('<div class="time-label"></div>');
              $container.append($assignment);
              window.planOutputPolish.upgradeAssignmentTitles(document);
              const assignmentTitle = $assignment.find('.task-title')[0];
              const assignmentStyles = getComputedStyle(assignmentTitle);

              const result = {
                hiddenArtifacts: hiddenArtifacts.length,
                artifactsStillDisplayed,
                mirrorText,
                sourceColor,
                repeatedColor,
                repeatedLessonName: $repeated.attr('data-lesson-name') || '',
                assignmentTag: assignmentTitle.tagName,
                assignmentValue: assignmentTitle.value || assignmentTitle.textContent || '',
                assignmentWhiteSpace: assignmentStyles.whiteSpace,
                assignmentOverflowWrap: assignmentStyles.overflowWrap,
                assignmentFontSize: Number.parseFloat(assignmentStyles.fontSize) || 0
              };

              $study.remove();
              $source.remove();
              $repeated.remove();
              $assignment.remove();
              return result;
            }
            """
        )
        require(
            visual_result["hiddenArtifacts"] >= 2 and visual_result["artifactsStillDisplayed"] == 0,
            "Select2 and resize editor rectangles are hidden in the PDF clone",
        )
        require(
            "فصل ۳ - تبادلات" in visual_result["mirrorText"] and "45 تست" in visual_result["mirrorText"],
            "PDF clone keeps chapter and test text while hiding editor controls",
        )
        require(
            visual_result["sourceColor"] == visual_result["repeatedColor"],
            "repeated study boxes preserve the exact source color",
        )
        require(
            visual_result["repeatedLessonName"] == "زیست",
            "repeated study box recovers its lesson identity",
        )
        require(
            visual_result["assignmentTag"] == "TEXTAREA",
            "event-derived assignment title uses a wrapping multiline control",
        )
        require(
            visual_result["assignmentValue"].startswith("آمادگی و تکلیف"),
            "long assignment title remains intact after wrapping upgrade",
        )
        require(
            visual_result["assignmentWhiteSpace"] in ("pre-wrap", "pre-wrap-auto"),
            "assignment title is allowed to wrap inside the box",
        )
        require(
            visual_result["assignmentFontSize"] <= 9.5,
            "assignment title uses compact readable typography",
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
