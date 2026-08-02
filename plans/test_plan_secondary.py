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
        start_style = b'/static/plans/plan-start-state.css?v='
        quarter_style = b'/static/plans/plan-quarter-snap-feedback.css?v='
        runtime = b'/static/plans/plan-runtime.js?v='
        secondary = b'/static/plans/plan-secondary.js?v='
        grid = b'/static/plans/plan-time-grid.js?v='
        interactions = b'/static/plans/plan-interactions.js?v='
        manual_resize = b'/static/plans/plan-manual-resize.js?v='
        drag_surface = b'/static/plans/plan-drag-surface.js?v='
        lesson_toolbar = b'/static/plans/plan-lesson-toolbar.js?v='
        task_geometry = b'/static/plans/plan-task-geometry.js?v='
        modern_ui = b'/static/plans/plan-modern-ui.js?v='
        start_state = b'/static/plans/plan-start-state.js?v='
        chapter_loader = b'/static/plans/plan-chapter-loader.js?v='
        quarter_feedback = b'/static/plans/plan-quarter-snap-feedback.js?v='

        markers = (
            interaction_style,
            grid_style,
            geometry_style,
            modern_style,
            modern_fixes_style,
            start_style,
            quarter_style,
            runtime,
            secondary,
            grid,
            interactions,
            manual_resize,
            drag_surface,
            lesson_toolbar,
            task_geometry,
            modern_ui,
            start_state,
            chapter_loader,
            quarter_feedback,
        )
        for marker in markers:
            self.assertEqual(content.count(marker), 1)

        for earlier, later in zip(markers, markers[1:]):
            self.assertLess(content.index(earlier), content.index(later))
        self.assertLess(content.index(quarter_feedback), content.rfind(b"</body>"))

        attributes = (
            b'data-plan-interactions="true"',
            b'data-plan-manual-resize="true"',
            b'data-plan-drag-surface="true"',
            b'data-plan-time-grid="true"',
            b'data-plan-lesson-toolbar="true"',
            b'data-plan-task-geometry="true"',
            b'data-plan-modern-ui="true"',
            b'data-plan-start-state="true"',
            b'data-plan-chapter-loader="true"',
            b'data-plan-quarter-snap-feedback="true"',
            b'data-plan-interactions-style="true"',
            b'data-plan-time-grid-style="true"',
            b'data-plan-task-geometry-style="true"',
            b'data-plan-modern-ui-style="true"',
            b'data-plan-modern-ui-fixes-style="true"',
            b'data-plan-start-state-style="true"',
            b'data-plan-quarter-snap-feedback-style="true"',
        )
        for attribute in attributes:
            self.assertIn(attribute, content)
