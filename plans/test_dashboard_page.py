from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import Profile


class DashboardResponsiveAssetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dashboard-responsive-admin",
            password="test-password",
            is_staff=True,
        )
        Profile.objects.create(
            user=self.user,
            role="admin",
            first_name="مدیر",
            last_name="ریسپانسیو",
        )
        self.client.force_login(self.user)

    def test_dashboard_responsive_stylesheet_is_injected_once(self):
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        content = response.content
        marker = b'data-dashboard-responsive-style="true"'
        asset = b'/static/plans/dashboard-responsive.css?v='
        self.assertEqual(content.count(marker), 1)
        self.assertEqual(content.count(asset), 1)
        self.assertLess(content.index(asset), content.rfind(b"</head>"))
        self.assertContains(response, 'id="chat-toggle-btn"')
