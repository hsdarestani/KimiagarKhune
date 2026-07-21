from django.contrib.auth import get_user_model
from django.test import TestCase

from plans.default_plan_data import ensure_advisor_for_user, seed_plan_defaults


class PlanSecondaryScriptTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username="plan-secondary-admin",
            email="plan-secondary@example.com",
            password="test-password",
        )
        advisor = ensure_advisor_for_user(self.admin)
        seed_plan_defaults(advisor=advisor)
        self.client.force_login(self.admin)

    def test_plan_assets_load_once_in_authoritative_order(self):
        response = self.client.get("/plan/")
        self.assertEqual(response.status_code, 200)
        content = response.content

        style = b'/static/plans/plan-interactions.css?v='
        runtime = b'/static/plans/plan-runtime.js?v='
        secondary = b'/static/plans/plan-secondary.js?v='
        interactions = b'/static/plans/plan-interactions.js?v='
        manual_resize = b'/static/plans/plan-manual-resize.js?v='

        for marker in (style, runtime, secondary, interactions, manual_resize):
            self.assertEqual(content.count(marker), 1)

        self.assertLess(content.index(style), content.index(runtime))
        self.assertLess(content.index(runtime), content.index(secondary))
        self.assertLess(content.index(secondary), content.index(interactions))
        self.assertLess(content.index(interactions), content.index(manual_resize))
        self.assertLess(content.index(manual_resize), content.rfind(b"</body>"))
        self.assertIn(b'data-plan-interactions="true"', content)
        self.assertIn(b'data-plan-manual-resize="true"', content)
        self.assertIn(b'data-plan-interactions-style="true"', content)
