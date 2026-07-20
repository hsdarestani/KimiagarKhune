from __future__ import annotations

from django.conf import settings
from django.contrib.auth.decorators import login_required

from plans import lesson_catalog


RUNTIME_PATHS = (
    ("plans/plan-runtime.js", "data-plan-runtime"),
    ("plans/plan-secondary.js", "data-plan-secondary"),
)


def _static_url(path: str) -> str:
    static_url = str(settings.STATIC_URL or "/static/")
    if not static_url.startswith(("/", "http://", "https://")):
        static_url = "/" + static_url
    return f"{static_url.rstrip('/')}/{path}"


def _append_runtime_scripts(response):
    """Append Plan scripts immediately before the real closing body.

    The legacy template contains literal ``</body>`` strings inside JavaScript
    template literals used for PDF windows. Therefore this intentionally uses
    the final closing body marker and never a first-match replacement.
    """

    content_type = response.get("Content-Type", "")
    if response.status_code != 200 or "text/html" not in content_type:
        return response

    scripts = b"\n".join(
        f'<script src="{_static_url(path)}" {attribute}="true"></script>'.encode(
            "utf-8"
        )
        for path, attribute in RUNTIME_PATHS
    )
    if all(
        f'{attribute}="true"'.encode("utf-8") in response.content
        for _path, attribute in RUNTIME_PATHS
    ):
        return response

    marker = b"</body>"
    marker_index = response.content.rfind(marker)
    if marker_index < 0:
        raise RuntimeError("The rendered Plan page has no closing body tag.")

    response.content = (
        response.content[:marker_index]
        + scripts
        + b"\n"
        + response.content[marker_index:]
    )
    response.headers.pop("Content-Length", None)
    return response


@login_required
def plan_view(request):
    response = lesson_catalog.plan_view(request)
    return _append_runtime_scripts(response)
