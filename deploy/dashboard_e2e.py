from __future__ import annotations

import os
import sys
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, sync_playwright


BASE_URL = os.environ.get(
    "DASHBOARD_BASE_URL", "https://panel.kimiagarkhoone.com"
).rstrip("/") + "/"
USERNAME = os.environ.get("DASHBOARD_USERNAME", "").strip()
PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def wait_for_content(page: Page, selector: str, minimum: int = 12) -> None:
    page.wait_for_function(
        """
        ({selector, minimum}) => {
          const element = document.querySelector(selector);
          return Boolean(
            element &&
            element.offsetParent !== null &&
            String(element.textContent || '').trim().length >= minimum
          );
        }
        """,
        arg={"selector": selector, "minimum": minimum},
        timeout=20_000,
    )


def main() -> int:
    if not USERNAME or not PASSWORD:
        print("DASHBOARD_USERNAME and DASHBOARD_PASSWORD are required.", file=sys.stderr)
        return 2

    page_errors: list[str] = []
    console_errors: list[str] = []
    first_party_failures: list[str] = []
    base_host = urlparse(BASE_URL).netloc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            locale="fa-IR",
            viewport={"width": 1440, "height": 1000},
            accept_downloads=True,
        )
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        def collect_console(message) -> None:
            if message.type == "error":
                text = message.text
                if "placehold.co" not in text and "favicon" not in text.lower():
                    console_errors.append(text)

        def collect_response(response) -> None:
            parsed = urlparse(response.url)
            if parsed.netloc != base_host or response.status < 400:
                return
            path = parsed.path
            if path.startswith(("/api/", "/courses/", "/sessions/", "/dashboard/")):
                first_party_failures.append(f"{response.status} {path}")

        page.on("console", collect_console)
        page.on("response", collect_response)

        page.goto(
            urljoin(BASE_URL, "login/"),
            wait_until="domcontentloaded",
            timeout=30_000,
        )
        page.fill("#username", USERNAME)
        page.fill("#password", PASSWORD)
        page.click('form button[type="submit"]')
        page.wait_for_url("**/plan/", timeout=30_000)
        page.goto(
            urljoin(BASE_URL, "dashboard/"),
            wait_until="domcontentloaded",
            timeout=30_000,
        )

        page.wait_for_function(
            """
            () => Boolean(
              document.querySelector('#calendar-grid') &&
              document.querySelector('#chat-toggle-btn') &&
              document.querySelector('#notifications-btn') &&
              document.querySelector('#open-admin-panel-btn')
            )
            """,
            timeout=20_000,
        )
        page.wait_for_function(
            "document.querySelectorAll('#calendar-grid .day-column').length === 7",
            timeout=30_000,
        )
        page.wait_for_selector("#admin-controls:not(.hidden)", timeout=20_000)

        require(page.locator("#calendar-grid .day-column").count() == 7, "weekly dashboard renders seven days")
        require(page.locator("#open-admin-panel-btn").is_visible(), "admin panel control is visible")
        require(page.locator("#advisor-filter").count() == 1, "advisor filter is present")
        require(page.locator("#role-indicator").inner_text().strip() != "", "active role indicator is rendered")

        api_checks = (
            ("/api/profile/", "application/json"),
            ("/courses/", "application/json"),
            ("/api/advisors/", "application/json"),
            ("/api/chat/conversations/", "application/json"),
            ("/api/notifications/inbox/", "application/json"),
            ("/api/admin-panel-data/", "application/json"),
            ("/api/admin/advisors/", "application/json"),
            ("/api/payments/", "application/json"),
            ("/api/reports/summary/", "application/json"),
        )
        for path, expected_type in api_checks:
            response = context.request.get(urljoin(BASE_URL, path.lstrip("/")))
            require(response.status == 200, f"{path} returns HTTP 200")
            require(expected_type in (response.headers.get("content-type") or ""), f"{path} returns {expected_type}")

        export_checks = (
            ("/api/reports/export/?section=advisor_performance&format=csv", "text/csv"),
            ("/api/reports/export/?section=advisor_performance&format=xlsx", "spreadsheetml"),
            ("/api/reports/export/?section=all&format=csv", "application/zip"),
        )
        for path, expected_type in export_checks:
            response = context.request.get(urljoin(BASE_URL, path.lstrip("/")))
            require(response.status == 200, f"{path} download endpoint works")
            require(expected_type in (response.headers.get("content-type") or ""), f"{path} has the correct content type")
            require(len(response.body()) > 20, f"{path} returns a non-empty file")

        page.click("#open-admin-panel-btn")
        page.wait_for_selector("#admin-panel-modal:not(.hidden)", timeout=10_000)
        for view_name in (
            "add-student",
            "assign-student",
            "manage-advisors",
            "send-notification",
            "reports",
            "financials",
        ):
            page.click(f'#admin-menu [data-view="{view_name}"]')
            wait_for_content(page, "#admin-panel-content")
            content = page.locator("#admin-panel-content").inner_text().strip()
            require("امکان بارگذاری اطلاعات وجود ندارد" not in content, f"admin view {view_name} loads without data error")
        page.click('[data-close-modal="admin-panel-modal"]')
        page.wait_for_selector("#admin-panel-modal.hidden", timeout=10_000)

        page.click("#chat-toggle-btn")
        page.wait_for_selector("#chat-window:not(.hidden)", timeout=10_000)
        require(page.locator("#chat-list").count() == 1, "chat conversation list opens")
        require(page.locator("#chat-file-btn").count() == 1, "chat file attachment control exists")
        require(page.locator("#chat-voice-btn").count() == 1, "chat voice control exists")
        page.click("#chat-toggle-btn")

        page.click("#notifications-btn")
        page.wait_for_selector("#notifications-modal:not(.hidden)", timeout=10_000)
        require(page.locator("#notifications-list").count() == 1, "notification inbox modal opens")
        page.click('[data-close-modal="notifications-modal"]')

        page.click("#profile-menu-btn")
        page.click("#open-profile-modal-btn")
        page.wait_for_selector("#profile-modal:not(.hidden)", timeout=10_000)
        require(page.locator("#profile-img-upload").count() == 1, "profile image editor opens")
        page.click('[data-close-modal="profile-modal"]')

        desktop = page.evaluate(
            """
            () => ({
              bodyOverflow: document.documentElement.scrollWidth - window.innerWidth,
              calendarScrollable: document.querySelector('.calendar-container').scrollWidth >= document.querySelector('.calendar-container').clientWidth,
              headerVisible: document.querySelector('header').offsetParent !== null
            })
            """
        )
        require(desktop["bodyOverflow"] <= 4, "dashboard has no severe desktop horizontal overflow")
        require(desktop["calendarScrollable"], "calendar remains reachable in its scroll region")
        require(desktop["headerVisible"], "dashboard header remains visible")

        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(400)
        mobile = page.evaluate(
            """
            () => {
              const container = document.querySelector('.calendar-container');
              const chat = document.querySelector('#chat-toggle-btn');
              return {
                bodyOverflow: document.documentElement.scrollWidth - window.innerWidth,
                calendarScrollable: container.scrollWidth > container.clientWidth,
                calendarWidth: container.getBoundingClientRect().width,
                chatVisible: chat.offsetParent !== null
              };
            }
            """
        )
        require(mobile["bodyOverflow"] <= 8, "mobile dashboard avoids severe global overflow")
        require(mobile["calendarScrollable"], "mobile weekly calendar scrolls horizontally")
        require(mobile["calendarWidth"] <= 391, "mobile calendar shell fits the viewport")
        require(mobile["chatVisible"], "mobile chat entry remains accessible")

        require(not first_party_failures, "dashboard generated no failing first-party requests: " + " | ".join(first_party_failures))
        require(not page_errors, "dashboard generated no uncaught JavaScript errors: " + " | ".join(page_errors))
        require(not console_errors, "dashboard generated no relevant console errors: " + " | ".join(console_errors))

        context.close()
        browser.close()

    print("Dashboard production regression completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
