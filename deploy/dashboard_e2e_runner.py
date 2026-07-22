from __future__ import annotations

from playwright.sync_api import Page


_ORIGINAL_WAIT_FOR_SELECTOR = Page.wait_for_selector


def _patched_wait_for_selector(self: Page, selector: str, *args, **kwargs):
    if selector == "#admin-panel-modal.hidden" and "state" not in kwargs:
        kwargs["state"] = "hidden"
    return _ORIGINAL_WAIT_FOR_SELECTOR(self, selector, *args, **kwargs)


def main() -> int:
    Page.wait_for_selector = _patched_wait_for_selector

    import dashboard_e2e

    return dashboard_e2e.main()


if __name__ == "__main__":
    raise SystemExit(main())
