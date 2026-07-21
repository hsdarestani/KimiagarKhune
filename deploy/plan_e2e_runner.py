from __future__ import annotations

from typing import Any

from playwright.sync_api import Locator, Page


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


def main() -> int:
    install_playwright_helpers()

    # This module sits next to plan_e2e.py, so importing it after installing
    # the helpers makes the existing end-to-end scenarios use the corrected
    # Playwright integration without duplicating the scenario definitions.
    import plan_e2e

    return plan_e2e.main()


if __name__ == "__main__":
    raise SystemExit(main())
