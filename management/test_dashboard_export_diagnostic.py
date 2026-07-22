from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import resolve, reverse

from accounts.models import Profile


class DashboardExportDiagnosticTests(TestCase):
    def test_export_route_and_response_diagnostics(self):
        user = User.objects.create_user(
            username="export-diagnostic-admin",
            password="test-password",
            is_staff=True,
        )
        Profile.objects.create(
            user=user,
            role="admin",
            first_name="Export",
            last_name="Diagnostic",
        )
        self.client.force_login(user)
        path = reverse("reports-export")
        match = resolve(path)
        response = self.client.get(
            path,
            {"section": "advisor_performance", "format": "csv"},
        )
        print("DASHBOARD_EXPORT_PATH", path)
        print("DASHBOARD_EXPORT_VIEW", match.func)
        print("DASHBOARD_EXPORT_STATUS", response.status_code)
        print("DASHBOARD_EXPORT_CONTENT_TYPE", response.get("Content-Type"))
        print("DASHBOARD_EXPORT_BODY", response.content[:1000])
        self.assertIsNotNone(match.func)
