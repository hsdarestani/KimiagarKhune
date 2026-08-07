from __future__ import annotations

import json
from datetime import date, time

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from accounts.models import Advisor, AdvisorAvailability, Grade, Major, Profile, School, Student
from plans.models import Course


class DashboardAssignmentAccessTests(TestCase):
    def setUp(self):
        self.grade = Grade.objects.create(name="یازدهم")
        self.major = Major.objects.create(name="ریاضی")
        self.school = School.objects.create(name="مدرسه تست تخصیص")

        self.admin = self._make_user("assignment-admin", "admin", is_staff=True)
        self.advisor_user = self._make_user("assignment-advisor", "advisor")
        self.advisor = Advisor.objects.create(profile=self.advisor_user.profile)
        self.other_advisor_user = self._make_user("assignment-other-advisor", "advisor")
        self.other_advisor = Advisor.objects.create(profile=self.other_advisor_user.profile)
        self.student_user = self._make_user("assignment-student", "student")
        self.student = Student.objects.create(
            profile=self.student_user.profile,
            school=self.school,
            major=self.major,
            grade=self.grade,
            advisor=None,
        )

        self.availability = AdvisorAvailability.objects.create(
            advisor=self.advisor,
            day_of_week="Monday",
            start_time=time(10, 0),
            end_time=time(11, 0),
            max_students=5,
        )

    def _make_user(self, username: str, role: str, *, is_staff: bool = False) -> User:
        user = User.objects.create_user(
            username=username,
            password="test-password",
            is_staff=is_staff,
        )
        Profile.objects.create(
            user=user,
            role=role,
            first_name=username,
            last_name="تست",
            phone_number=f"09{user.pk:09d}"[-11:],
        )
        return user

    def _assign(self):
        self.client.force_login(self.admin)
        return self.client.post(
            "/api/assign-student/",
            data=json.dumps(
                {
                    "student_id": self.student.pk,
                    "advisor_id": self.advisor.pk,
                    "day_of_week": "Monday",
                    "start_time": "10:00",
                    "start_date": "2026-08-10",
                }
            ),
            content_type="application/json",
        )

    def _assert_advisor_can_use_student_across_surfaces(self):
        self.client.force_login(self.advisor_user)

        chat = self.client.get(f"/api/chat/messages/user:{self.student_user.pk}/")
        self.assertEqual(chat.status_code, 200, chat.content)

        plan_page = self.client.get("/plan/")
        self.assertEqual(plan_page.status_code, 200, plan_page.content)
        student_ids = {student.pk for student in plan_page.context["students"]}
        self.assertIn(self.student.pk, student_ids)

        lessons = self.client.get(
            "/get-lessons-for-student/", {"student_id": self.student.pk}
        )
        self.assertEqual(lessons.status_code, 200, lessons.content)

        check = self.client.get(
            "/check-weekly-report/",
            {"student_id": self.student.pk, "selected_date": "2026-08-10"},
        )
        self.assertEqual(check.status_code, 200, check.content)

        report = self.client.get(
            "/get-weekly-report-details/",
            {"student_id": self.student.pk, "week_start": "2026-08-10"},
        )
        self.assertEqual(report.status_code, 200, report.content)

    def test_dashboard_assignment_persists_student_advisor_and_grants_every_surface(self):
        response = self._assign()
        self.assertEqual(response.status_code, 201, response.content)

        self.student.refresh_from_db()
        self.assertEqual(self.student.advisor_id, self.advisor.pk)
        course = Course.objects.get(student=self.student, advisor=self.advisor)
        self.assertEqual(course.sessions.count(), 4)

        self._assert_advisor_can_use_student_across_surfaces()

        self.client.force_login(self.student_user)
        student_chat = self.client.get(
            f"/api/chat/messages/user:{self.advisor_user.pk}/"
        )
        self.assertEqual(student_chat.status_code, 200, student_chat.content)

        denied = self.client.get(
            f"/api/chat/messages/user:{self.other_advisor_user.pk}/"
        )
        self.assertEqual(denied.status_code, 403)

    def test_legacy_course_assignment_is_allowed_across_plan_and_chat_before_repair(self):
        Course.objects.create(
            student=self.student,
            advisor=self.advisor,
            day_of_week="Monday",
            start_time=time(10, 0),
            start_date=date(2026, 8, 10),
            is_active=True,
        )
        self.assertIsNone(self.student.advisor_id)

        self._assert_advisor_can_use_student_across_surfaces()

        self.client.force_login(self.student_user)
        response = self.client.get(
            f"/api/chat/messages/user:{self.advisor_user.pk}/"
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_unrelated_advisor_is_denied_across_plan_and_chat(self):
        response = self._assign()
        self.assertEqual(response.status_code, 201, response.content)
        self.client.force_login(self.other_advisor_user)

        self.assertEqual(
            self.client.get(f"/api/chat/messages/user:{self.student_user.pk}/").status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                "/get-lessons-for-student/", {"student_id": self.student.pk}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                "/check-weekly-report/",
                {"student_id": self.student.pk, "selected_date": "2026-08-10"},
            ).status_code,
            403,
        )

    def test_repair_command_backfills_latest_active_course_advisor(self):
        Course.objects.create(
            student=self.student,
            advisor=self.other_advisor,
            day_of_week="Tuesday",
            start_time=time(9, 0),
            start_date=date(2026, 7, 1),
            is_active=True,
        )
        Course.objects.create(
            student=self.student,
            advisor=self.advisor,
            day_of_week="Monday",
            start_time=time(10, 0),
            start_date=date(2026, 8, 10),
            is_active=True,
        )

        call_command("repair_student_advisor_assignments")
        self.student.refresh_from_db()
        self.assertEqual(self.student.advisor_id, self.advisor.pk)

        self.client.force_login(self.other_advisor_user)
        denied = self.client.get(
            f"/api/chat/messages/user:{self.student_user.pk}/"
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.advisor_user)
        allowed = self.client.get(
            f"/api/chat/messages/user:{self.student_user.pk}/"
        )
        self.assertEqual(allowed.status_code, 200, allowed.content)
