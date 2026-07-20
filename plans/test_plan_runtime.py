import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Student
from plans.default_plan_data import ensure_advisor_for_user, seed_plan_defaults
from plans.models import Box, WeeklyReport, WeeklyReportDetail
from plans.weekly_plans import normalize_day_name
from plans.weekly_plans_v2 import date_for_day


class PlanRuntimeRegressionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username="plan-runtime-admin",
            email="plan-runtime@example.com",
            password="test-password",
        )
        self.advisor = ensure_advisor_for_user(self.admin)
        seed_plan_defaults(advisor=self.advisor)
        self.student = Student.objects.get(
            profile__user__username="demo_plan_student_t"
        )
        self.target_student = Student.objects.get(
            profile__user__username="demo_plan_student_r"
        )
        self.client.force_login(self.admin)

    def test_runtime_is_appended_after_legacy_scripts(self):
        response = self.client.get("/plan/")
        self.assertEqual(response.status_code, 200)
        content = response.content

        runtime_marker = b'/static/plans/plan-runtime.js'
        self.assertEqual(content.count(runtime_marker), 1)
        runtime_index = content.index(runtime_marker)
        final_body_index = content.rfind(b"</body>")
        previous_script_index = content.rfind(b"</script>", 0, runtime_index)

        self.assertGreater(previous_script_index, 0)
        self.assertGreater(runtime_index, previous_script_index)
        self.assertGreater(final_body_index, runtime_index)
        self.assertNotIn(b"plan-defaults.js", content)
        self.assertIn(b"function initCalendarTask", content)
        self.assertIn(b"function updateTimeLabel", content)

    def test_day_names_are_normalized_without_silent_saturday_fallback(self):
        self.assertEqual(normalize_day_name("یکشنبه"), "یک‌شنبه")
        self.assertEqual(normalize_day_name("سه شنبه"), "سه‌شنبه")
        self.assertEqual(normalize_day_name("پنج\u200cشنبه"), "پنج‌شنبه")
        self.assertIsNone(normalize_day_name("روز نامعتبر"))

    def test_selected_start_day_is_calendar_offset_zero(self):
        self.assertEqual(
            date_for_day(
                __import__("datetime").date(2038, 1, 6),
                "چهارشنبه",
            ).isoformat(),
            "2038-01-06",
        )

        payload = {
            "student_id": self.student.pk,
            "week_start": "2038-01-06",
            "week_end": "2038-01-12",
            "days": [
                {
                    "day": "چهارشنبه",
                    "disabled": False,
                    "tasks": [
                        {
                            "title": "روز اول واقعی",
                            "start": "08:00:00",
                            "end": "09:00:00",
                            "box_type": "ایونت",
                        }
                    ],
                },
                {
                    "day": "پنجشنبه",
                    "disabled": False,
                    "tasks": [
                        {
                            "title": "روز دوم واقعی",
                            "start": "10:00:00",
                            "end": "11:00:00",
                            "box_type": "ایونت",
                        }
                    ],
                },
                {
                    "day": "سه شنبه",
                    "disabled": False,
                    "tasks": [
                        {
                            "title": "روز هفتم واقعی",
                            "start": "12:00:00",
                            "end": "13:00:00",
                            "box_type": "ایونت",
                        }
                    ],
                },
            ],
        }
        response = self.client.post(
            "/save-weekly-report/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        dates = {
            detail.box.name: detail.start_time.date().isoformat()
            for detail in WeeklyReportDetail.objects.filter(
                report__student=self.student
            ).select_related("box")
        }
        self.assertEqual(dates["روز اول واقعی"], "2038-01-06")
        self.assertEqual(dates["روز دوم واقعی"], "2038-01-07")
        self.assertEqual(dates["روز هفتم واقعی"], "2038-01-12")

    def test_save_and_reload_preserves_types_times_duration_and_selected_week(self):
        payload = {
            "student_id": self.student.pk,
            "week_start": "2038-01-02",
            "week_end": "2038-01-08",
            "important_events": "آزمون ذخیره و بازیابی",
            "days": [
                {
                    "day": "شنبه",
                    "disabled": False,
                    "tasks": [
                        {
                            "title": "جلسه مشاوره",
                            "start": "08:15:00",
                            "end": "09:45:00",
                            "box_type": "ایونت",
                            "duration_minutes": 90,
                        },
                        {
                            "title": "یادداشت آزاد",
                            "start": "10:00:00",
                            "end": "10:30:00",
                            "box_type": "شناور",
                            "duration_minutes": 30,
                        },
                    ],
                },
                {
                    "day": "یکشنبه",
                    "disabled": False,
                    "tasks": [
                        {
                            "title": "تکلیف مدرسه",
                            "start": "23:00:00",
                            "end": "00:00:00",
                            "box_type": "تکلیف",
                            "duration_minutes": 60,
                        }
                    ],
                },
                {
                    "day": "سه شنبه",
                    "disabled": True,
                    "tasks": [],
                },
            ],
        }

        response = self.client.post(
            "/save-weekly-report/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["week_start"], "2038-01-02")
        self.assertEqual(body["tasks_count"], 3)

        report = WeeklyReport.objects.get(pk=body["report_id"])
        self.assertEqual(report.week_start.date().isoformat(), "2038-01-02")
        self.assertEqual(report.week_end.date().isoformat(), "2038-01-08")
        self.assertEqual(report.disabled_days, "سه‌شنبه")
        self.assertEqual(report.important_events, "آزمون ذخیره و بازیابی")

        event_box = Box.objects.get(name="جلسه مشاوره")
        self.assertFalse(event_box.is_default)
        self.assertEqual(event_box.duration_minutes, 90)
        self.assertEqual(event_box.box_type.name, "ایونت")

        overnight = WeeklyReportDetail.objects.get(box__name="تکلیف مدرسه")
        self.assertEqual(overnight.day_of_week, "یک‌شنبه")
        self.assertEqual(
            int((overnight.end_time - overnight.start_time).total_seconds() // 60),
            60,
        )
        self.assertEqual(overnight.box.box_type.name, "تکلیف")

        details_response = self.client.get(
            "/get-weekly-report-details/",
            {
                "student_id": self.student.pk,
                "week_start": "2038-01-02T00:00:00+00:00",
            },
        )
        self.assertEqual(details_response.status_code, 200, details_response.content)
        details = details_response.json()
        self.assertEqual(details["report_id"], report.pk)
        self.assertEqual(details["disabled_days"], ["سه‌شنبه"])
        self.assertEqual(
            {task["box_type"] for task in details["tasks"]},
            {"ایونت", "شناور", "تکلیف"},
        )
        self.assertEqual(
            {task["day_of_week"] for task in details["tasks"]},
            {"شنبه", "یک‌شنبه"},
        )

        updated_payload = {
            **payload,
            "important_events": "نسخه دوم",
            "days": [
                {
                    "day": "شنبه",
                    "disabled": False,
                    "tasks": [
                        {
                            "title": "نسخه دوم ایونت",
                            "start": "12:00:00",
                            "end": "13:00:00",
                            "box_type": "ایونت",
                            "duration_minutes": 60,
                        }
                    ],
                }
            ],
        }
        second_response = self.client.post(
            "/save-weekly-report/",
            data=json.dumps(updated_payload),
            content_type="application/json",
        )
        self.assertEqual(second_response.status_code, 200, second_response.content)
        self.assertEqual(
            WeeklyReport.objects.filter(student=self.student).count(), 1
        )
        self.assertFalse(Box.objects.filter(name="جلسه مشاوره").exists())
        self.assertTrue(
            Box.objects.filter(name="نسخه دوم ایونت", is_default=False).exists()
        )

    def test_invalid_day_is_rejected_instead_of_saved_as_saturday(self):
        response = self.client.post(
            "/save-weekly-report/",
            data=json.dumps(
                {
                    "student_id": self.student.pk,
                    "week_start": "2038-02-01",
                    "week_end": "2038-02-07",
                    "days": [
                        {
                            "day": "روز نامعتبر",
                            "disabled": False,
                            "tasks": [],
                        }
                    ],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            WeeklyReport.objects.filter(
                student=self.student,
                week_start__date="2038-02-01",
            ).exists()
        )

    def test_copy_day_accepts_day_alias_and_adjusts_target_date(self):
        source_payload = {
            "student_id": self.student.pk,
            "week_start": "2038-03-06",
            "week_end": "2038-03-12",
            "days": [
                {
                    "day": "شنبه",
                    "disabled": False,
                    "tasks": [
                        {
                            "title": "باکس قابل کپی",
                            "start": "09:00:00",
                            "end": "10:30:00",
                            "box_type": "ایونت",
                            "duration_minutes": 90,
                        }
                    ],
                }
            ],
        }
        source_response = self.client.post(
            "/save-weekly-report/",
            data=json.dumps(source_payload),
            content_type="application/json",
        )
        self.assertEqual(
            source_response.status_code, 200, source_response.content
        )

        copy_response = self.client.post(
            "/copy_day_plan/",
            {
                "source_student_id": self.student.pk,
                "target_student_id": self.target_student.pk,
                "source_date": "2038-03-06",
                "target_day_of_week": "یکشنبه",
            },
        )
        self.assertEqual(copy_response.status_code, 200, copy_response.content)
        copied = WeeklyReportDetail.objects.get(
            report__student=self.target_student,
            box__name="باکس قابل کپی",
        )
        self.assertEqual(copied.day_of_week, "یک‌شنبه")
        self.assertEqual(copied.start_time.date().isoformat(), "2038-03-07")
        self.assertEqual(copied.start_time.strftime("%H:%M"), "09:00")
        self.assertEqual(copied.end_time.strftime("%H:%M"), "10:30")
