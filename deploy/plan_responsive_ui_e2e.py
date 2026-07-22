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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def main() -> int:
    if not USERNAME or not PASSWORD:
        print("PLAN_USERNAME and PLAN_PASSWORD are required.", file=sys.stderr)
        return 2

    page_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            locale="fa-IR",
            viewport={"width": 1440, "height": 1000},
        )
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        page.goto(
            urljoin(BASE_URL, "login/"),
            wait_until="domcontentloaded",
            timeout=30_000,
        )
        page.fill("#username", USERNAME)
        page.fill("#password", PASSWORD)
        page.click('form button[type="submit"]')
        page.wait_for_url("**/plan/", timeout=30_000)
        page.wait_for_function(
            "window.planModernUi && "
            "document.body.classList.contains('plan-ui-modern') && "
            "document.querySelector('[data-plan-modern-ui-style=true]')",
            timeout=20_000,
        )

        desktop = page.evaluate(
            """
            () => {
              const body = document.body;
              const header = document.querySelector('.top-header');
              const palette = document.querySelector('.plan-palette-row');
              const sidebar = document.querySelector('.subjects-box');
              const wrapper = document.querySelector('.calendar-wrapper');
              return {
                modern: body.classList.contains('plan-ui-modern'),
                heading: Boolean(document.querySelector('.plan-page-heading')),
                palette: Boolean(palette && palette.contains(document.querySelector('.assignments-box')) && palette.contains(document.querySelector('.events-box'))),
                sidebarPosition: sidebar ? getComputedStyle(sidebar).position : '',
                toggleDisplay: getComputedStyle(document.querySelector('.plan-subjects-toggle')).display,
                headerWidth: header ? header.getBoundingClientRect().width : 0,
                wrapperWidth: wrapper ? wrapper.getBoundingClientRect().width : 0,
                viewport: window.innerWidth
              };
            }
            """
        )
        require(desktop["modern"], "modern Plan visual layer is active")
        require(desktop["heading"], "new Plan heading is rendered")
        require(desktop["palette"], "assignment and event palettes share one visual row")
        require(desktop["sidebarPosition"] == "sticky", "lesson sidebar is sticky on desktop")
        require(desktop["toggleDisplay"] == "none", "mobile lesson button stays hidden on desktop")
        require(desktop["headerWidth"] <= desktop["viewport"] + 1, "desktop header fits the viewport")
        require(desktop["wrapperWidth"] > 500, "desktop calendar keeps a useful workspace width")

        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(350)
        mobile = page.evaluate(
            """
            () => {
              const html = document.documentElement;
              const wrapper = document.querySelector('.calendar-wrapper');
              const toggle = document.querySelector('.plan-subjects-toggle');
              const subjects = document.querySelector('.subjects-box');
              const week = document.querySelector('.week-selector');
              return {
                bodyOverflow: html.scrollWidth - window.innerWidth,
                toggleVisible: toggle && getComputedStyle(toggle).display !== 'none',
                toggleExpanded: toggle && toggle.getAttribute('aria-expanded'),
                sidebarHidden: subjects && subjects.getAttribute('aria-hidden'),
                calendarScrollable: wrapper && wrapper.scrollWidth > wrapper.clientWidth,
                weekScrollable: week && week.scrollWidth >= week.clientWidth,
                wrapperWidth: wrapper ? wrapper.getBoundingClientRect().width : 0,
                viewport: window.innerWidth
              };
            }
            """
        )
        require(mobile["bodyOverflow"] <= 2, "mobile page has no global horizontal overflow")
        require(mobile["toggleVisible"], "mobile lesson drawer button is visible")
        require(mobile["toggleExpanded"] == "false", "mobile lesson drawer starts closed")
        require(mobile["sidebarHidden"] == "true", "closed mobile lesson drawer is hidden accessibly")
        require(mobile["calendarScrollable"], "weekly calendar scrolls inside its own mobile region")
        require(mobile["weekScrollable"], "week and PDF controls remain reachable by horizontal scroll")
        require(mobile["wrapperWidth"] <= mobile["viewport"] + 1, "mobile calendar shell fits the viewport")

        page.click(".plan-subjects-toggle")
        page.wait_for_function("document.body.classList.contains('plan-subjects-open')")
        opened = page.evaluate(
            """
            () => {
              const sidebar = document.querySelector('.subjects-box');
              const backdrop = document.querySelector('.plan-mobile-backdrop');
              const rect = sidebar.getBoundingClientRect();
              return {
                expanded: document.querySelector('.plan-subjects-toggle').getAttribute('aria-expanded'),
                hidden: sidebar.getAttribute('aria-hidden'),
                left: rect.left,
                right: rect.right,
                width: rect.width,
                backdropOpacity: Number.parseFloat(getComputedStyle(backdrop).opacity)
              };
            }
            """
        )
        require(opened["expanded"] == "true", "lesson drawer exposes its open state")
        require(opened["hidden"] == "false", "open lesson drawer is available to assistive technology")
        require(opened["left"] >= 0 and opened["right"] <= 391, "lesson drawer stays inside the mobile viewport")
        require(opened["width"] >= 280, "lesson drawer keeps a comfortable touch width")
        require(opened["backdropOpacity"] > 0.5, "mobile lesson drawer has a visible backdrop")

        page.keyboard.press("Escape")
        page.wait_for_function("!document.body.classList.contains('plan-subjects-open')")
        require(
            page.locator(".plan-subjects-toggle").get_attribute("aria-expanded") == "false",
            "Escape closes the lesson drawer",
        )

        require(
            not page_errors,
            "responsive visual layer produces no uncaught JavaScript errors: "
            + " | ".join(page_errors),
        )

        context.close()
        browser.close()

    print("Responsive Plan UI regression completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
