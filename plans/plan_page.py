from __future__ import annotations

from django.conf import settings
from django.contrib.auth.decorators import login_required

from plans import lesson_catalog


ASSET_VERSION = "20260721-3"
STYLE_PATHS = (
    ("plans/plan-interactions.css", "data-plan-interactions-style"),
)
RUNTIME_PATHS = (
    ("plans/plan-runtime.js", "data-plan-runtime"),
    ("plans/plan-secondary.js", "data-plan-secondary"),
    ("plans/plan-interactions.js", "data-plan-interactions"),
    ("plans/plan-manual-resize.js", "data-plan-manual-resize"),
)


def _static_url(path: str) -> str:
    static_url = str(settings.STATIC_URL or "/static/")
    if not static_url.startswith(("/", "http://", "https://")):
        static_url = "/" + static_url
    return f"{static_url.rstrip('/')}/{path}?v={ASSET_VERSION}"


def _append_runtime_assets(response):
    """Append Plan assets without matching HTML snippets embedded in PDF scripts.

    The legacy template contains literal closing body/head tags inside JavaScript
    strings. Assets are therefore inserted only before the final real body tag.
    """

    content_type = response.get("Content-Type", "")
    if response.status_code != 200 or "text/html" not in content_type:
        return response

    styles = b"\n".join(
        f'<link rel="stylesheet" href="{_static_url(path)}" {attribute}="true">'.encode(
            "utf-8"
        )
        for path, attribute in STYLE_PATHS
    )
    scripts = b"\n".join(
        f'<script src="{_static_url(path)}" {attribute}="true"></script>'.encode(
            "utf-8"
        )
        for path, attribute in RUNTIME_PATHS
    )
    assets = styles + b"\n" + scripts

    attributes = [attribute for _path, attribute in STYLE_PATHS + RUNTIME_PATHS]
    if all(
        f'{attribute}="true"'.encode("utf-8") in response.content
        for attribute in attributes
    ):
        return response

    marker = b"</body>"
    marker_index = response.content.rfind(marker)
    if marker_index < 0:
        raise RuntimeError("The rendered Plan page has no closing body tag.")

    response.content = (
        response.content[:marker_index]
        + assets
        + b"\n"
        + response.content[marker_index:]
    )
    response.headers.pop("Content-Length", None)
    return response


@login_required
def plan_view(request):
    response = lesson_catalog.plan_view(request)
    return _append_runtime_assets(response)
