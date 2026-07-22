from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import Student
from plans.default_plan_data import ensure_advisor_for_user, seed_plan_defaults
from plans.models import Box, BoxType, DefaultEvent, WeeklyReport


class PlanDefaultSeedTests(TestCase):
    def test_default_data_is_present_and_idempotent(self):
        expected_box_names = {
            "ایونت",
            "باکس شناور",
            "آزمون آزمایشی",
            "تحلیل آزمون",
            "پیش آزمون و تحلیل آن",
            "مرور و آمادگی آزمون",
        }

        self.assertEqual(
            set(
                BoxType.objects.filter(is_default=True).values_list(
                    "name", flat=True
                )
            ),
            {"مطالعه", "ایونت", "تکلیف", "شناور"},
        )
        self.assertEqual(
            set(
                Box.objects.filter(
                    is_default=True,
                    lesson__isnull=True,
                    chapter__isnull=True,
                ).values_list("name", flat=True)
            ),
            expected_box_names,
        )
        self.assertEqual(
            Student.objects.filter(
                profile__user__username__startswith="demo_plan_student_"
            ).count(),
            3,
        )
        self.assertEqual(
            DefaultEvent.objects.filter(
                student__profile__user__username__startswith="demo_plan_student_"
            ).count(),
            15,
        )

        call_command("seed_plan_defaults", verbosity=0)

        self.assertEqual(
            Box.objects.filter(
                is_default=True,
                lesson__isnull=True,
                chapter__isnull=True,
                name__in=expected_box_names,
            ).count(),
            6,
        )
        self.assertEqual(
            Student.objects.filter(
                profile__user__username__startswith="demo_plan_student_"
            ).count(),
            3,
        )
        self.assertEqual(
            DefaultEvent.objects.filter(
                student__profile__user__username__startswith="demo_plan_student_"
            ).count(),
            15,
        )

    def test_admin_can_read_default_palette_and_student_events(self):
        User = get_user_model()
        admin = User.objects.create_superuser(
            username="plan-admin",
            email="admin@example.com",
            password="test-password",
        )
        advisor = ensure_advisor_for_user(admin)
        seed_plan_defaults(advisor=advisor)
        student = Student.objects.get(
            profile__user__username="demo_plan_student_t"
        )

        self.client.force_login(admin)

        plan_response = self.client.get("/plan/")
        self.assertEqual(plan_response.status_code, 200)
        self.assertNotContains(plan_response, "/static/plans/plan-defaults.js")
        self.assertContains(plan_response, "function initCalendarTask")
        self.assertContains(plan_response, "function updateTimeLabel")
        self.assertContains(plan_response, "نمونه تجربی دوازدهم")

        palette_response = self.client.get("/get_default_boxes/")
        self.assertEqual(palette_response.status_code, 200)
        palette = palette_response.json()
        self.assertEqual(len(palette["event_boxes"]), 2)
        self.assertEqual(len(palette["exam_boxes"]), 4)

        events_response = self.client.get(
            "/get_default_events/",
            {"student_id": student.pk},
        )
        self.assertEqual(events_response.status_code, 200)
        events = events_response.json()
        self.assertEqual(len(events), 5)
        self.assertTrue(all(event["name"] == "مدرسه" for event in events))

    def test_far_future_reports_are_cleaned_only_for_demo_students(self):
        User = get_user_model()
        admin = User.objects.create_superuser(
            username="cleanup-admin",
            email="cleanup@example.com",
            password="test-password",
        )
        advisor = ensure_advisor_for_user(admin)
        seed_plan_defaults(advisor=advisor)
        demo_student = Student.objects.get(
            profile__user__username="demo_plan_student_t"
        )

        now = timezone.now()
        near_report = WeeklyReport.objects.create(
            student=demo_student,
            week_start=now + timedelta(days=30),
            week_end=now + timedelta(days=36),
        )
        far_report = WeeklyReport.objects.create(
            student=demo_student,
            week_start=now + timedelta(days=4000),
            week_end=now + timedelta(days=4006),
        )

        call_command("cleanup_plan_demo_reports", verbosity=0)

        self.assertTrue(WeeklyReport.objects.filter(pk=near_report.pk).exists())
        self.assertFalse(WeeklyReport.objects.filter(pk=far_report.pk).exists())
