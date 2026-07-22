from __future__ import annotations

from django.conf import settings
from django.contrib.auth.decorators import login_required

from plans import views


ASSET_VERSION = "20260722-1"
STYLE_ATTRIBUTE = "data-dashboard-responsive-style"
STYLE_PATH = "plans/dashboard-responsive.css"


def _static_url(path: str) -> str:
    static_url = str(settings.STATIC_URL or "/static/")
    if not static_url.startswith(("/", "http://", "https://")):
        static_url = "/" + static_url
    return f"{static_url.rstrip('/')}/{path}?v={ASSET_VERSION}"


def _append_dashboard_assets(response):
    content_type = response.get("Content-Type", "")
    if response.status_code != 200 or "text/html" not in content_type:
        return response

    marker_attribute = f'{STYLE_ATTRIBUTE}="true"'.encode("utf-8")
    if marker_attribute in response.content:
        return response

    marker = b"</head>"
    marker_index = response.content.rfind(marker)
    if marker_index < 0:
        raise RuntimeError("The rendered Dashboard page has no closing head tag.")

    style = (
        f'<link rel="stylesheet" href="{_static_url(STYLE_PATH)}" '
        f'{STYLE_ATTRIBUTE}="true">\n'
    ).encode("utf-8")
    response.content = (
        response.content[:marker_index]
        + style
        + response.content[marker_index:]
    )
    response.headers.pop("Content-Length", None)
    return response


@login_required
def dashboard_view(request):
    response = views.dashboard_view(request)
    return _append_dashboard_assets(response)
