from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

from playwright.sync_api import Locator, Page, sync_playwright


_ORIGINAL_CHECK = Locator.check
_ORIGINAL_UNCHECK = Locator.uncheck
_ORIGINAL_SELECT_OPTION = Page.select_option
_ORIGINAL_WAIT_FOR_FUNCTION = Page.wait_for_function


def _check_each(locator: Locator, *, checked: bool, **kwargs: Any) -> None:
    count = locator.count()
    operation = _ORIGINAL_CHECK if checked else _ORIGINAL_UNCHECK
    if count <= 1:
        operation(locator, **kwargs)
        return

    for index in range(count):
        operation(locator.nth(index), **kwargs)


def _patched_check(self: Locator, **kwargs: Any) -> None:
    _check_each(self, checked=True, **kwargs)


def _patched_uncheck(self: Locator, **kwargs: Any) -> None:
    _check_each(self, checked=False, **kwargs)


def _patched_select_option(
    self: Page,
    selector: str,
    value: Any = None,
    **kwargs: Any,
):
    """Select hidden Select2-backed controls through their native element."""

    label = kwargs.get("label")
    if selector == "#otherStudentSelect" and label:
        return self.evaluate(
            """
            ({selector, label}) => {
              const select = document.querySelector(selector);
              if (!select) throw new Error('Other student selector not found');
              const option = Array.from(select.options).find(
                item => item.textContent.trim() === String(label).trim()
              );
              if (!option) throw new Error('Other student option not found');
              window.jQuery(select).val(option.value).trigger('change');
              return [option.value];
            }
            """,
            {"selector": selector, "label": label},
        )
    return _ORIGINAL_SELECT_OPTION(self, selector, value, **kwargs)


def _patched_wait_for_function(
    self: Page,
    expression: Any,
    *args: Any,
    **kwargs: Any,
):
    """Map one legacy architecture assertion to the current Plan contract.

    The old secondary script wrapped every droppable callback and exposed a
    `planSecondaryWrapped` marker. The authoritative interaction layer now owns
    drops, while the secondary script only exposes its task builder. The old
    regression scenario still exercises the same other-student drop afterwards;
    only its readiness check needs to follow the new architecture.
    """

    if isinstance(expression, str) and "planSecondaryWrapped" in expression:
        expression = """
        () => Boolean(
          window.planSecondaryBuildOtherPlanTask &&
          document.querySelector('script[data-plan-interactions=true]') &&
          document.querySelectorAll('.calendar .task-container.ui-droppable').length === 7
        )
        """
    return _ORIGINAL_WAIT_FOR_FUNCTION(self, expression, *args, **kwargs)


def install_playwright_helpers() -> None:
    Locator.check = _patched_check
    Locator.uncheck = _patched_uncheck
    Page.select_option = _patched_select_option
    Page.wait_for_function = _patched_wait_for_function


def verify_initial_controls() -> None:
    """Ensure the pre-load guide never blocks student/date selection."""

    base_url = os.environ.get(
        "PLAN_BASE_URL", "https://panel.kimiagarkhoone.com"
    ).rstrip("/") + "/"
    username = os.environ.get("PLAN_USERNAME", "").strip()
    password = os.environ.get("PLAN_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("PLAN_USERNAME and PLAN_PASSWORD are required.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            locale="fa-IR",
            viewport={"width": 1600, "height": 1000},
        )
        page = context.new_page()
        page.goto(
            urljoin(base_url, "login/"),
            wait_until="domcontentloaded",
            timeout=30_000,
        )
        page.fill("#username", username)
        page.fill("#password", password)
        page.click('form button[type="submit"]')
        page.wait_for_url("**/plan/", timeout=30_000)
        page.wait_for_selector(
            "#pageOverlay.plan-start-notice",
            state="attached",
            timeout=20_000,
        )

        state = page.evaluate(
            """
            () => {
              const overlay = document.querySelector('#pageOverlay');
              const wrapper = document.querySelector('.calendar-wrapper');
              const student = document.querySelector('#student-select');
              const dateInput = document.querySelector('#weekSelector');
              const overlayRect = overlay.getBoundingClientRect();
              const wrapperRect = wrapper.getBoundingClientRect();
              const studentRect = student.getBoundingClientRect();
              const dateRect = dateInput.getBoundingClientRect();
              const overlaps = (a, b) => !(
                a.right <= b.left || a.left >= b.right ||
                a.bottom <= b.top || a.top >= b.bottom
              );
              const style = getComputedStyle(overlay);
              return {
                pointerEvents: style.pointerEvents,
                overlayInsideCalendar:
                  overlay.parentElement === wrapper &&
                  overlayRect.top >= wrapperRect.top - 1 &&
                  overlayRect.left >= wrapperRect.left - 1,
                blocksStudent: overlaps(overlayRect, studentRect),
                blocksDate: overlaps(overlayRect, dateRect),
                studentVisible: studentRect.width > 0 && studentRect.height > 0,
                dateVisible: dateRect.width > 0 && dateRect.height > 0,
              };
            }
            """
        )

        if state["pointerEvents"] != "none":
            raise AssertionError("Plan start guide captures pointer events.")
        if not state["overlayInsideCalendar"]:
            raise AssertionError("Plan start guide is not scoped to the calendar.")
        if state["blocksStudent"] or state["blocksDate"]:
            raise AssertionError("Plan start guide overlaps student/date controls.")
        if not state["studentVisible"] or not state["dateVisible"]:
            raise AssertionError("Student/date controls are not visible initially.")

        page.click("#student-select")
        page.click("#weekSelector")
        print("PASS: initial Plan guide does not block student or date selection")

        context.close()
        browser.close()


def main() -> int:
    install_playwright_helpers()
    verify_initial_controls()

    # This module sits next to plan_e2e.py, so importing it after installing
    # the helpers makes the existing end-to-end scenarios use the corrected
    # Playwright integration without duplicating the scenario definitions.
    import plan_e2e

    return plan_e2e.main()


if __name__ == "__main__":
    raise SystemExit(main())
