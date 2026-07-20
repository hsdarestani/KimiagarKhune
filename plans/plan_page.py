from __future__ import annotations

from django.conf import settings
from django.contrib.auth.decorators import login_required

from plans import lesson_catalog


RUNTIME_PATH = "plans/plan-runtime.js"


def _runtime_url() -> str:
    static_url = str(settings.STATIC_URL or "/static/")
    if not static_url.startswith(("/", "http://", "https://")):
        static_url = "/" + static_url
    return f"{static_url.rstrip('/')}/{RUNTIME_PATH}"


def _append_runtime_script(response):
    """Append the isolated Plan runtime immediately before the real closing body.

    The legacy template contains literal ``</body>`` strings inside JavaScript
    template literals used for PDF windows. Therefore this intentionally uses
    the final closing body marker and never a first-match replacement.
    """

    content_type = response.get("Content-Type", "")
    if response.status_code != 200 or "text/html" not in content_type:
        return response

    script = f'<script src="{_runtime_url()}" data-plan-runtime="true"></script>'.encode(
        "utf-8"
    )
    if script in response.content:
        return response

    marker = b"</body>"
    marker_index = response.content.rfind(marker)
    if marker_index < 0:
        raise RuntimeError("The rendered Plan page has no closing body tag.")

    response.content = (
        response.content[:marker_index]
        + script
        + b"\n"
        + response.content[marker_index:]
    )
    response.headers.pop("Content-Length", None)
    return response


@login_required
def plan_view(request):
    response = lesson_catalog.plan_view(request)
    return _append_runtime_script(response)
