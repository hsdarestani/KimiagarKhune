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

    def test_secondary_script_loads_after_core_runtime_and_before_real_body_end(self):
        response = self.client.get("/plan/")
        self.assertEqual(response.status_code, 200)
        content = response.content

        runtime = b'/static/plans/plan-runtime.js'
        secondary = b'/static/plans/plan-secondary.js'
        self.assertEqual(content.count(runtime), 1)
        self.assertEqual(content.count(secondary), 1)
        self.assertLess(content.index(runtime), content.index(secondary))
        self.assertLess(content.index(secondary), content.rfind(b"</body>"))
