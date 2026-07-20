from __future__ import annotations

from typing import Any

from playwright.sync_api import Locator, Page


_ORIGINAL_CHECK = Locator.check
_ORIGINAL_UNCHECK = Locator.uncheck
_ORIGINAL_SELECT_OPTION = Page.select_option


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
    """Select hidden Select2-backed controls through their native element.

    Playwright correctly refuses to operate on the hidden native select in
    strict user-action mode. The application itself changes Select2 values by
    updating that select and triggering `change`, so the regression runner uses
    the same integration path for the other-student selector.
    """

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


def install_playwright_helpers() -> None:
    Locator.check = _patched_check
    Locator.uncheck = _patched_uncheck
    Page.select_option = _patched_select_option


def main() -> int:
    install_playwright_helpers()

    # This module sits next to plan_e2e.py, so importing it after installing
    # the helpers makes the existing end-to-end scenarios use the corrected
    # Playwright integration without duplicating the scenario definitions.
    import plan_e2e

    return plan_e2e.main()


if __name__ == "__main__":
    raise SystemExit(main())
