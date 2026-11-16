"""Regressions for changing a student's school timetable and exporting it."""
import datetime as dt
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Student
from plans.default_plan_data import ensure_advisor_for_user, seed_plan_defaults
from plans.models import Box, BoxType, DefaultEvent, WeeklyReport, WeeklyReportDetail


class SchoolScheduleRegressionTests(TestCase):
    days = ("شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه")

    def setUp(self):
        user = get_user_model().objects.create_superuser(
            username="schedule-regression-admin",
            email="school-schedule-regression@example.com",
            password="test-password",
        )
        advisor = ensure_advisor_for_user(user)
        seed_plan_defaults(advisor=advisor)
        self.student = Student.objects.get(
            profile__user__username="demo_plan_student_t"
        )
        self.client.force_login(user)

    def save(self, start, end, event_tasks, removed_days=None):
        payload = {
            "student_id": self.student.pk,
            "week_start": start,
            "week_end": end,
            "removed_recurring_event_days": removed_days or [],
            "days": [
                {
                    "day": day,
                    "disabled": False,
                    "tasks": event_tasks if day == "دوشنبه" else [],
                }
                for day in self.days
            ],
        }
        response = self.client.post(
            "/save-weekly-report/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        return WeeklyReport.objects.get(pk=response.json()["report_id"])

    def default_events(self):
        response = self.client.get(
            "/get_default_events/", {"student_id": self.student.pk}
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def monday_events(self):
        """Only the updated school day; other days are intentionally retained."""
        return [
            event for event in self.default_events()
            if event["day_of_week"] == "دوشنبه"
        ]

    def test_rescheduling_school_class_does_not_restore_old_schedule(self):
        first = self.save("2039-04-02", "2039-04-08", [{
            "title": "مدرسه قدیمی",
            "start": "07:30", "end": "09:00", "box_type": "ایونت",
        }])
        self.save("2039-04-09", "2039-04-15", [{
            "title": "مدرسه جدید",
            "start": "09:15", "end": "10:45", "box_type": "ایونت",
        }])
        self.assertEqual(self.monday_events(), [{
            "name": "مدرسه جدید",
            "day_of_week": "دوشنبه",
            "start_time": "09:15",
            "end_time": "10:45",
        }])
        self.assertTrue(DefaultEvent.objects.filter(
            student=self.student, name="مدرسه قدیمی", is_active=False
        ).exists())
        self.assertTrue(WeeklyReportDetail.objects.filter(
            report=first, box__name="مدرسه قدیمی"
        ).exists())

        # Explicitly removing the loaded event on Monday deactivates that class,
        # without destroying historical reports or reintroducing legacy events.
        self.save("2039-04-16", "2039-04-22", [], removed_days=["دوشنبه"])
        self.assertEqual(self.monday_events(), [])
        self.assertTrue(WeeklyReportDetail.objects.filter(
            report=first, box__name="مدرسه قدیمی"
        ).exists())

    def test_study_only_week_does_not_clear_existing_school_recurrence(self):
        self.save("2039-04-02", "2039-04-08", [{
            "title": "مدرسه ثابت",
            "start": "08:00", "end": "09:00", "box_type": "ایونت",
        }])
        self.save("2039-04-09", "2039-04-15", [])
        self.assertEqual(self.monday_events(), [{
            "name": "مدرسه ثابت",
            "day_of_week": "دوشنبه",
            "start_time": "08:00", "end_time": "09:00",
        }])

    def test_adding_monday_class_preserves_thursday_recurrence(self):
        DefaultEvent.objects.create(
            student=self.student,
            name="کلاس پنجشنبه",
            day_of_week="پنج‌شنبه",
            start_time=dt.time(14, 0),
            end_time=dt.time(15, 30),
        )
        self.save("2039-04-02", "2039-04-08", [{
            "title": "کلاس دوشنبه",
            "start": "10:00", "end": "11:00", "box_type": "ایونت",
        }])
        # An event added on Monday must never erase Thursdays recurring class.
        self.assertTrue(DefaultEvent.objects.get(
            student=self.student, name="کلاس پنجشنبه"
        ).is_active)

    def test_eventless_newer_legacy_week_blocks_old_fallback(self):
        DefaultEvent.objects.filter(student=self.student).delete()
        old = WeeklyReport.objects.create(
            student=self.student,
            week_start=timezone.make_aware(dt.datetime(2039, 5, 1)),
            week_end=timezone.make_aware(dt.datetime(2039, 5, 7, 23, 59)),
        )
        event = Box.objects.create(
            box_type=BoxType.objects.get(name="ایونت"),
            name="مدرسه دیگر وجود ندارد", duration_minutes=60, is_default=False,
        )
        WeeklyReportDetail.objects.create(
            report=old,
            box=event,
            start_time=timezone.make_aware(dt.datetime(2039, 5, 2, 8)),
            end_time=timezone.make_aware(dt.datetime(2039, 5, 2, 9)),
            day_of_week="دوشنبه",
        )
        WeeklyReport.objects.create(
            student=self.student,
            week_start=timezone.make_aware(dt.datetime(2039, 5, 8)),
            week_end=timezone.make_aware(dt.datetime(2039, 5, 14, 23, 59)),
        )
        self.assertEqual(self.default_events(), [])

    def test_pdf_collects_live_calendar_not_stale_wrapper(self):
        source = (
            Path(__file__).parent / "static" / "plans" / "plan-export-v2.js"
        ).read_text(encoding="utf-8")
        self.assertIn("$('.calendar > .day-column')", source)
        self.assertNotIn("$('.calendar-wrapper .day-column')", source)
        self.assertIn("runtime.studentId", source)
