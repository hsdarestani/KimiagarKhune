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

        interaction_style = b'/static/plans/plan-interactions.css?v='
        grid_style = b'/static/plans/plan-time-grid.css?v='
        geometry_style = b'/static/plans/plan-task-geometry.css?v='
        modern_style = b'/static/plans/plan-modern-ui.css?v='
        modern_fixes_style = b'/static/plans/plan-modern-ui-fixes.css?v='
        runtime = b'/static/plans/plan-runtime.js?v='
        secondary = b'/static/plans/plan-secondary.js?v='
        grid = b'/static/plans/plan-time-grid.js?v='
        interactions = b'/static/plans/plan-interactions.js?v='
        manual_resize = b'/static/plans/plan-manual-resize.js?v='
        drag_surface = b'/static/plans/plan-drag-surface.js?v='
        lesson_toolbar = b'/static/plans/plan-lesson-toolbar.js?v='
        task_geometry = b'/static/plans/plan-task-geometry.js?v='
        modern_ui = b'/static/plans/plan-modern-ui.js?v='

        markers = (
            interaction_style,
            grid_style,
            geometry_style,
            modern_style,
            modern_fixes_style,
            runtime,
            secondary,
            grid,
            interactions,
            manual_resize,
            drag_surface,
            lesson_toolbar,
            task_geometry,
            modern_ui,
        )
        for marker in markers:
            self.assertEqual(content.count(marker), 1)

        for earlier, later in zip(markers, markers[1:]):
            self.assertLess(content.index(earlier), content.index(later))
        self.assertLess(content.index(modern_ui), content.rfind(b"</body>"))

        self.assertIn(b'data-plan-interactions="true"', content)
        self.assertIn(b'data-plan-manual-resize="true"', content)
        self.assertIn(b'data-plan-drag-surface="true"', content)
        self.assertIn(b'data-plan-time-grid="true"', content)
        self.assertIn(b'data-plan-lesson-toolbar="true"', content)
        self.assertIn(b'data-plan-task-geometry="true"', content)
        self.assertIn(b'data-plan-modern-ui="true"', content)
        self.assertIn(b'data-plan-interactions-style="true"', content)
        self.assertIn(b'data-plan-time-grid-style="true"', content)
        self.assertIn(b'data-plan-task-geometry-style="true"', content)
        self.assertIn(b'data-plan-modern-ui-style="true"', content)
        self.assertIn(b'data-plan-modern-ui-fixes-style="true"', content)
