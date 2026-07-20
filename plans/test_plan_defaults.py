from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from accounts.models import Student
from plans.default_plan_data import ensure_advisor_for_user, seed_plan_defaults
from plans.models import Box, BoxType, DefaultEvent


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
