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
STUDENT_LABEL = os.environ.get("PLAN_GRID_STUDENT_LABEL", "نمونه ریاضی یازدهم")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def box(locator: Locator) -> dict[str, float]:
    value = locator.bounding_box()
    if not value:
        raise AssertionError("Element has no visible bounding box")
    return value


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
        "window.planChapterLoader && "
        "document.body.dataset.planChapterLoaderVersion",
        timeout=20_000,
    )


def drag_palette_to(page: Page, source: Locator, target: Locator) -> None:
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
        target_box["y"] + 230,
        steps=28,
    )
    page.mouse.up()
    page.wait_for_timeout(500)


def main() -> int:
    if not USERNAME or not PASSWORD:
        print("PLAN_USERNAME and PLAN_PASSWORD are required.", file=sys.stderr)
        return 2

    errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(locale="fa-IR", viewport={"width": 1440, "height": 950})
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

        containers = page.locator(".calendar .task-container")
        target = None
        for index in range(containers.count()):
            candidate = containers.nth(index)
            if candidate.locator(":scope > .calendar-task").count() == 0:
                target = candidate
                break
        require(target is not None, "an empty calendar day is available")

        palette = page.locator(".subjects-box .plan-lesson-palette:visible").first
        require(palette.count() == 1, "a visible lesson is available")
        lesson_id = palette.get_attribute("data-lesson-id")
        require(bool(lesson_id), "lesson palette exposes lesson id")

        drag_palette_to(page, palette, target)
        task = target.locator(
            f':scope > .calendar-task[data-lesson-id="{lesson_id}"]'
        ).first
        require(task.count() == 1, "lesson card is created")

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

        chapter_select = task.locator(".task-chapter")
        select2 = chapter_select.locator(
            "xpath=following-sibling::*[contains(@class, 'select2-container')]"
        ).first
        require(select2.count() == 1, "chapter Select2 exists inside the lesson card")

        rendered_before = select2.locator(".select2-selection__rendered").first
        require(rendered_before.is_visible(), "chapter field itself is visible in the lesson card")
        initial_style = rendered_before.evaluate(
            """
            element => {
              const style = getComputedStyle(element);
              return {
                color: style.color,
                opacity: Number.parseFloat(style.opacity || '1'),
                fontSize: Number.parseFloat(style.fontSize || '0'),
                text: String(element.textContent || '').trim()
              };
            }
            """
        )
        require(initial_style["opacity"] >= 0.95, "chapter field text is not transparent")
        require(initial_style["fontSize"] >= 9, "chapter field text has a readable font size")
        require(bool(initial_style["text"]), "chapter field shows a visible placeholder or selection")

        select2.click()
        page.wait_for_selector(".select2-dropdown.plan-chapter-dropdown", state="visible", timeout=10_000)
        page.wait_for_function(
            """
            () => Array.from(document.querySelectorAll('.plan-chapter-dropdown .select2-results__option'))
              .some(option => {
                const text = String(option.textContent || '').trim();
                return text && !option.classList.contains('loading-results');
              })
            """,
            timeout=10_000,
        )

        dropdown = page.locator(".select2-dropdown.plan-chapter-dropdown:visible").last
        dropdown_box = box(dropdown)
        require(dropdown_box["width"] >= 250, "chapter dropdown is wide enough to read real headings")
        require(dropdown_box["x"] >= -1, "chapter dropdown stays inside the left viewport edge")
        require(
            dropdown_box["x"] + dropdown_box["width"] <= 1441,
            "chapter dropdown stays inside the right viewport edge",
        )

        options = dropdown.locator(".select2-results__option")
        visible_option = None
        for index in range(options.count()):
            candidate = options.nth(index)
            text = candidate.inner_text().strip()
            if text and "در حال" not in text:
                visible_option = candidate
                break
        require(visible_option is not None, "at least one real chapter heading is rendered")
        require(visible_option.is_visible(), "chapter heading is visibly rendered, not only present in DOM")

        option_style = visible_option.evaluate(
            """
            element => {
              const style = getComputedStyle(element);
              const rect = element.getBoundingClientRect();
              return {
                color: style.color,
                backgroundColor: style.backgroundColor,
                opacity: Number.parseFloat(style.opacity || '1'),
                visibility: style.visibility,
                display: style.display,
                fontSize: Number.parseFloat(style.fontSize || '0'),
                lineHeight: Number.parseFloat(style.lineHeight || '0'),
                width: rect.width,
                height: rect.height,
                text: String(element.textContent || '').trim()
              };
            }
            """
        )
        require(option_style["display"] != "none", "chapter heading is not display:none")
        require(option_style["visibility"] != "hidden", "chapter heading is not visibility:hidden")
        require(option_style["opacity"] >= 0.95, "chapter heading is opaque")
        require(option_style["fontSize"] >= 11, "chapter heading uses readable typography")
        require(option_style["height"] >= 30, "chapter row has enough visible height")
        require(len(option_style["text"]) >= 2, "chapter row contains visible heading text")

        chosen_text = option_style["text"]
        visible_option.click()
        page.wait_for_timeout(250)

        display_state = task.evaluate(
            """
            element => {
              const visible = node => {
                if (!node) return false;
                const style = getComputedStyle(node);
                const rect = node.getBoundingClientRect();
                return style.display !== 'none' &&
                  style.visibility !== 'hidden' &&
                  Number.parseFloat(style.opacity || '1') > 0 &&
                  rect.width > 0 && rect.height > 0;
              };

              const compact = element.querySelector('.plan-study-compact');
              const chip = element.querySelector('.plan-chapter-chip');
              if (visible(compact) && visible(chip)) {
                return {
                  source: 'compact',
                  text: String(chip.textContent || '').trim()
                };
              }

              const chapter = element.querySelector('.task-chapter');
              let container = chapter ? chapter.nextElementSibling : null;
              while (container && !container.classList.contains('select2-container')) {
                container = container.nextElementSibling;
              }
              const rendered = container
                ? container.querySelector('.select2-selection__rendered')
                : null;
              return {
                source: 'editor',
                text: visible(rendered)
                  ? String(rendered.textContent || '').trim()
                  : ''
              };
            }
            """
        )
        display_text = display_state["text"]
        require(bool(display_text), "selected chapter heading remains visibly rendered inside the lesson card")
        require(
            chosen_text in display_text or display_text in chosen_text,
            "lesson card visibly displays the chapter that was selected",
        )
        print(f"PASS: selected chapter is shown through {display_state['source']} mode")
        require(not errors, "chapter visibility flow has no uncaught JavaScript errors: " + " | ".join(errors))

        context.close()
        browser.close()

    print("Plan chapter visibility regression completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
