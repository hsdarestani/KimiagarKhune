import datetime as dt
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Student
from plans.default_plan_data import ensure_advisor_for_user, seed_plan_defaults
from plans.models import Box, BoxType, Lesson, LessonType, WeeklyReport, WeeklyReportDetail


class PlanPersistenceRegressionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username="plan-persistence-admin",
            email="plan-persistence@example.com",
            password="test-password",
        )
        self.advisor = ensure_advisor_for_user(self.admin)
        seed_plan_defaults(advisor=self.advisor)
        self.student = Student.objects.get(
            profile__user__username="demo_plan_student_t"
        )
        self.client.force_login(self.admin)

    def aware(self, year, month, day, hour=0, minute=0):
        value = dt.datetime(year, month, day, hour, minute)
        return timezone.make_aware(value, timezone.get_current_timezone())

    def test_plan_page_loads_persistence_runtime(self):
        response = self.client.get("/plan/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/plans/plan-persistence-fixes.js?v=20260818-1")
        self.assertContains(response, 'data-plan-persistence-fixes="true"')

    def test_event_and_event_assignment_titles_round_trip_exactly(self):
        payload = {
            "student_id": self.student.pk,
            "week_start": "2039-01-01",
            "week_end": "2039-01-07",
            "days": [
                {
                    "day": "شنبه",
                    "disabled": False,
                    "tasks": [
                        {
                            "title": "کلاس فیزیک دهم",
                            "start": "10:00:00",
                            "end": "11:30:00",
                            "box_type": "ایونت",
                        },
                        {
                            "title": "آمادگی و تکلیف کلاس فیزیک دهم",
                            "start": "18:30:00",
                            "end": "19:00:00",
                            "box_type": "تکلیف",
                        },
                    ],
                }
            ],
        }
        save_response = self.client.post(
            "/save-weekly-report/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(save_response.status_code, 200, save_response.content)

        report = WeeklyReport.objects.get(pk=save_response.json()["report_id"])
        self.assertEqual(
            set(report.details.values_list("box__name", flat=True)),
            {"کلاس فیزیک دهم", "آمادگی و تکلیف کلاس فیزیک دهم"},
        )

        reload_response = self.client.get(
            "/get-weekly-report-details/",
            {"student_id": self.student.pk, "week_start": "2039-01-01"},
        )
        self.assertEqual(reload_response.status_code, 200, reload_response.content)
        self.assertEqual(
            {task["title"] for task in reload_response.json()["tasks"]},
            {"کلاس فیزیک دهم", "آمادگی و تکلیف کلاس فیزیک دهم"},
        )

    def test_reuse_uses_latest_report_that_actually_contains_study(self):
        lesson_type, _ = LessonType.objects.get_or_create(name="اختصاصی")
        lesson = Lesson.objects.create(
            subject_code="PERSIST-BIO-11",
            name="زیست یازدهم تست پایداری",
            lesson_type=lesson_type,
            grade=self.student.grade,
        )
        study_type = BoxType.objects.get(name="مطالعه")
        event_type = BoxType.objects.get(name="ایونت")

        reusable_report = WeeklyReport.objects.create(
            student=self.student,
            week_start=self.aware(2039, 2, 5),
            week_end=self.aware(2039, 2, 11, 23, 59),
        )
        study_box = Box.objects.create(
            box_type=study_type,
            lesson=lesson,
            name=lesson.name,
            duration_minutes=90,
            optional_tests_count=25,
            is_default=False,
        )
        WeeklyReportDetail.objects.create(
            report=reusable_report,
            box=study_box,
            start_time=self.aware(2039, 2, 5, 16, 0),
            end_time=self.aware(2039, 2, 5, 17, 30),
            day_of_week="شنبه",
        )

        # This is newer, but it is only a class/event. The old implementation
        # selected this report first and then returned an empty study list.
        newer_event_report = WeeklyReport.objects.create(
            student=self.student,
            week_start=self.aware(2039, 2, 12),
            week_end=self.aware(2039, 2, 18, 23, 59),
        )
        event_box = Box.objects.create(
            box_type=event_type,
            name="کلاس ثابت",
            duration_minutes=60,
            is_default=False,
        )
        WeeklyReportDetail.objects.create(
            report=newer_event_report,
            box=event_box,
            start_time=self.aware(2039, 2, 12, 9, 0),
            end_time=self.aware(2039, 2, 12, 10, 0),
            day_of_week="شنبه",
        )

        # An even newer empty save must not hide the reusable plan either.
        WeeklyReport.objects.create(
            student=self.student,
            week_start=self.aware(2039, 2, 19),
            week_end=self.aware(2039, 2, 25, 23, 59),
        )

        response = self.client.get(
            "/get-last-weekly-report/",
            {"student_id": self.student.pk},
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["report_id"], reusable_report.pk)
        self.assertEqual(len(body["tasks"]), 1)
        task = body["tasks"][0]
        self.assertEqual(task["lesson_id"], lesson.pk)
        self.assertEqual(task["lesson_name"], lesson.name)
        self.assertEqual(task["duration_minutes"], 90)
        self.assertEqual(task["optional_tests_count"], 25)
        self.assertEqual(task["day_of_week"], "شنبه")
