from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from datetime import date, time, timedelta
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from accounts.models import Advisor, AdvisorAvailability, Grade, Major, Profile, School, Student
from management.models import ChatMessage, NotificationRecipient, Payment
from plans.models import Comment, Course, Session


MEDIA_ROOT = tempfile.mkdtemp(prefix="dashboard-tests-")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class DashboardFeatureTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.grade = Grade.objects.create(name="یازدهم")
        self.major = Major.objects.create(name="ریاضی")
        self.school = School.objects.create(name="مدرسه تست")

        self.admin_user, self.admin_profile = self._user_with_profile(
            "dash-admin", "admin", is_staff=True, first_name="مدیر"
        )
        self.advisor_user, advisor_profile = self._user_with_profile(
            "dash-advisor", "advisor", first_name="مشاور"
        )
        self.advisor = Advisor.objects.create(profile=advisor_profile)
        self.other_advisor_user, other_advisor_profile = self._user_with_profile(
            "other-advisor", "advisor", first_name="مشاور دوم"
        )
        self.other_advisor = Advisor.objects.create(profile=other_advisor_profile)

        self.student_user, student_profile = self._user_with_profile(
            "dash-student", "student", first_name="دانش‌آموز"
        )
        self.student = Student.objects.create(
            profile=student_profile,
            school=self.school,
            major=self.major,
            grade=self.grade,
            advisor=self.advisor,
        )
        self.other_student_user, other_student_profile = self._user_with_profile(
            "other-student", "student", first_name="دانش‌آموز دوم"
        )
        self.other_student = Student.objects.create(
            profile=other_student_profile,
            school=self.school,
            major=self.major,
            grade=self.grade,
            advisor=self.other_advisor,
        )

        self.availability = AdvisorAvailability.objects.create(
            advisor=self.advisor,
            day_of_week="Monday",
            start_time=time(10, 0),
            end_time=time(11, 0),
            max_students=2,
        )
        AdvisorAvailability.objects.create(
            advisor=self.other_advisor,
            day_of_week="Tuesday",
            start_time=time(12, 0),
            end_time=time(13, 0),
            max_students=1,
        )

        self.course = Course.objects.create(
            student=self.student,
            advisor=self.advisor,
            day_of_week="Monday",
            start_time=time(10, 0),
            start_date=date(2026, 7, 20),
        )
        for number in range(1, 5):
            Session.objects.create(
                course=self.course,
                session_number=number,
                date=self.course.start_date + timedelta(days=7 * (number - 1)),
            )

    def _user_with_profile(self, username, role, *, is_staff=False, first_name="کاربر"):
        user = User.objects.create_user(
            username=username,
            password="test-password",
            is_staff=is_staff,
        )
        profile = Profile.objects.create(
            user=user,
            role=role,
            first_name=first_name,
            last_name="تست",
            phone_number=f"09{user.pk:09d}"[-11:],
        )
        return user, profile

    def login(self, user):
        self.client.force_login(user)

    def post_json(self, path, payload):
        return self.client.post(
            path,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def patch_json(self, path, payload):
        return self.client.patch(
            path,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_dashboard_renders_role_context_and_requires_login(self):
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 302)

        for user, expected_role in (
            (self.admin_user, "admin"),
            (self.advisor_user, "advisor"),
            (self.student_user, "student"),
        ):
            self.login(user)
            response = self.client.get("/dashboard/")
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'id="calendar-grid"')
            self.assertContains(response, 'id="chat-toggle-btn"')
            self.assertContains(response, f'"role": "{expected_role}"')
            self.client.logout()

    def test_admin_data_and_account_creation_are_admin_only(self):
        self.login(self.student_user)
        self.assertEqual(self.client.get("/api/admin-panel-data/").status_code, 403)
        self.assertEqual(
            self.post_json(
                "/api/add-student/",
                {
                    "first_name": "جدید",
                    "last_name": "دانش‌آموز",
                    "phone_number": "09120000001",
                    "major_id": self.major.pk,
                    "grade_id": self.grade.pk,
                },
            ).status_code,
            403,
        )

        self.login(self.admin_user)
        response = self.client.get("/api/admin-panel-data/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("students", response.json())
        self.assertIn("advisors", response.json())

        response = self.post_json(
            "/api/add-student/",
            {
                "first_name": "جدید",
                "last_name": "دانش‌آموز",
                "phone_number": "09120000001",
                "major_id": self.major.pk,
                "grade_id": self.grade.pk,
            },
        )
        self.assertEqual(response.status_code, 201, response.content)
        created_user = User.objects.get(username="09120000001")
        self.assertFalse(created_user.has_usable_password())
        self.assertTrue(Student.objects.filter(profile__user=created_user).exists())

        duplicate = self.post_json(
            "/api/add-student/",
            {
                "first_name": "تکراری",
                "last_name": "کاربر",
                "phone_number": "09120000001",
                "major_id": self.major.pk,
                "grade_id": self.grade.pk,
            },
        )
        self.assertEqual(duplicate.status_code, 400)

    def test_advisor_creation_availability_and_assignment(self):
        self.login(self.admin_user)
        response = self.post_json(
            "/api/admin/advisors/",
            {
                "first_name": "مشاور",
                "last_name": "جدید",
                "phone_number": "09120000002",
                "working_hours": [
                    {
                        "day_of_week": "Wednesday",
                        "start_time": "14:00",
                        "end_time": "15:00",
                        "max_students": 2,
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 201, response.content)
        advisor = Advisor.objects.get(profile__user__username="09120000002")
        self.assertFalse(advisor.profile.user.has_usable_password())
        self.assertEqual(advisor.availabilities.count(), 1)

        new_student_user, new_profile = self._user_with_profile(
            "assign-student", "student", first_name="برای تخصیص"
        )
        new_student = Student.objects.create(
            profile=new_profile,
            school=self.school,
            major=self.major,
            grade=self.grade,
        )
        response = self.post_json(
            "/api/assign-student/",
            {
                "student_id": new_student.pk,
                "advisor_id": advisor.pk,
                "day_of_week": "Wednesday",
                "start_time": "14:00",
                "start_date": "2026-07-22",
            },
        )
        self.assertEqual(response.status_code, 201, response.content)
        assigned_course = Course.objects.get(student=new_student, advisor=advisor)
        self.assertEqual(assigned_course.sessions.count(), 4)

    def test_course_and_session_permissions_and_updates(self):
        self.login(self.student_user)
        courses = self.client.get("/courses/")
        self.assertEqual(courses.status_code, 200)
        ids = {item["id"] for item in courses.json()}
        self.assertEqual(ids, {self.course.pk})

        comment = self.client.post(
            f"/courses/{self.course.pk}/add-comment/",
            {"text": "نظر دانش‌آموز"},
        )
        self.assertEqual(comment.status_code, 201, comment.content)
        self.assertTrue(Comment.objects.filter(course=self.course, text="نظر دانش‌آموز").exists())

        outsider = self.client.get(f"/courses/{Course.objects.create(student=self.other_student, advisor=self.other_advisor, day_of_week='Tuesday', start_time=time(12, 0), start_date=date(2026, 7, 21)).pk}/")
        self.assertEqual(outsider.status_code, 404)

        upload = self.client.post(
            f"/sessions/{self.course.sessions.first().pk}/upload-plan/",
            {"plan_file": SimpleUploadedFile("plan.pdf", b"pdf-data", content_type="application/pdf")},
        )
        self.assertEqual(upload.status_code, 403)

        self.login(self.advisor_user)
        upload = self.client.post(
            f"/sessions/{self.course.sessions.first().pk}/upload-plan/",
            {"plan_file": SimpleUploadedFile("plan.pdf", b"pdf-data", content_type="application/pdf")},
        )
        self.assertEqual(upload.status_code, 200, upload.content)

        schedule_attempt = self.patch_json(
            f"/courses/{self.course.pk}/",
            {"day_of_week": "Monday", "start_time": "10:00", "start_date": "2026-07-27"},
        )
        self.assertEqual(schedule_attempt.status_code, 403)

        self.login(self.admin_user)
        moved = self.patch_json(
            f"/courses/{self.course.pk}/",
            {"day_of_week": "Monday", "start_time": "10:00", "start_date": "2026-07-27"},
        )
        self.assertEqual(moved.status_code, 200, moved.content)
        dates = list(self.course.sessions.order_by("session_number").values_list("date", flat=True))
        self.assertEqual(dates, [date(2026, 7, 27) + timedelta(days=7 * i) for i in range(4)])

    def test_completing_fourth_session_creates_payment_notification(self):
        fourth = self.course.sessions.get(session_number=4)
        first_three = self.course.sessions.exclude(pk=fourth.pk)
        first_three.update(is_completed=True)

        self.login(self.advisor_user)
        with patch("plans.views.send_telegram_message"), patch("plans.views.send_sms_message"):
            response = self.patch_json(
                f"/sessions/{fourth.pk}/",
                {"is_completed": True},
            )
        self.assertEqual(response.status_code, 200, response.content)
        self.course.refresh_from_db()
        self.assertTrue(self.course.payment_notification_sent)
        self.assertTrue(
            NotificationRecipient.objects.filter(user=self.student_user).exists()
        )

    def test_chat_is_limited_to_assigned_relationships_and_supports_attachments(self):
        self.login(self.student_user)
        conversations = self.client.get("/api/chat/conversations/")
        self.assertEqual(conversations.status_code, 200)
        ids = {item["id"] for item in conversations.json()}
        self.assertIn(f"user:{self.advisor_user.pk}", ids)
        self.assertNotIn(f"user:{self.other_advisor_user.pk}", ids)

        allowed = self.client.post(
            f"/api/chat/messages/user:{self.advisor_user.pk}/",
            {"text": "سلام مشاور"},
        )
        self.assertEqual(allowed.status_code, 201, allowed.content)

        denied = self.client.get(
            f"/api/chat/messages/user:{self.other_advisor_user.pk}/"
        )
        self.assertEqual(denied.status_code, 403)
        denied_post = self.client.post(
            f"/api/chat/messages/user:{self.other_advisor_user.pk}/",
            {"text": "نباید ارسال شود"},
        )
        self.assertEqual(denied_post.status_code, 403)

        file_message = self.client.post(
            f"/api/chat/messages/user:{self.advisor_user.pk}/",
            {"file": SimpleUploadedFile("note.txt", b"hello", content_type="text/plain")},
        )
        self.assertEqual(file_message.status_code, 201, file_message.content)
        self.assertTrue(ChatMessage.objects.filter(file__isnull=False).exclude(file="").exists())

        pair = self.client.get(
            f"/api/chat/messages/pair:{self.advisor_user.pk}:{self.student_user.pk}/"
        )
        self.assertEqual(pair.status_code, 403)

        self.login(self.admin_user)
        pair = self.client.get(
            f"/api/chat/messages/pair:{self.advisor_user.pk}:{self.student_user.pk}/"
        )
        self.assertEqual(pair.status_code, 200, pair.content)

    def test_payments_submit_history_and_admin_review(self):
        self.login(self.student_user)
        submitted = self.post_json(
            "/api/payments/submit/",
            {
                "amount": 450000,
                "reference_number": "REF-1",
                "payment_date": "2026-07-22",
                "course": self.course.pk,
            },
        )
        self.assertEqual(submitted.status_code, 201, submitted.content)
        payment = Payment.objects.get(reference_number="REF-1")
        self.assertEqual(payment.student, self.student)
        self.assertEqual(payment.status, "pending")

        own = self.client.get("/api/payments/mine/")
        self.assertEqual(own.status_code, 200)
        self.assertEqual([item["id"] for item in own.json()], [payment.pk])

        self.login(self.advisor_user)
        self.assertEqual(self.client.get("/api/payments/mine/").json(), [])
        advisor_submit = self.post_json(
            "/api/payments/submit/",
            {"amount": 1, "reference_number": "X", "payment_date": "2026-07-22"},
        )
        self.assertEqual(advisor_submit.status_code, 400)

        self.login(self.admin_user)
        payments = self.client.get("/api/payments/")
        self.assertEqual(payments.status_code, 200)
        approve = self.client.post(f"/api/payments/{payment.pk}/approve/")
        self.assertEqual(approve.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "approved")
        reject = self.client.post(
            f"/api/payments/{payment.pk}/reject/",
            {"notes": "نامعتبر"},
        )
        self.assertEqual(reject.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "rejected")
        self.assertEqual(payment.admin_notes, "نامعتبر")

    def test_notifications_inbox_and_mark_read(self):
        self.login(self.admin_user)
        recipients = self.client.get("/api/notifications/recipients/")
        self.assertEqual(recipients.status_code, 200)
        response = self.post_json(
            "/api/notifications/send/",
            {
                "message": "اعلان تست",
                "channels": ["panel"],
                "recipient_ids": [self.student_user.pk],
            },
        )
        self.assertEqual(response.status_code, 201, response.content)

        self.login(self.student_user)
        inbox = self.client.get("/api/notifications/inbox/")
        self.assertEqual(inbox.status_code, 200)
        self.assertEqual(len(inbox.json()), 1)
        recipient_id = inbox.json()[0]["id"]
        marked = self.post_json(
            "/api/notifications/mark-read/", {"ids": [recipient_id]}
        )
        self.assertEqual(marked.status_code, 200)
        self.assertEqual(marked.json()["updated"], 1)
        self.assertTrue(NotificationRecipient.objects.get(pk=recipient_id).is_read)
        self.assertEqual(
            self.post_json(
                "/api/notifications/send/",
                {"message": "غیرمجاز", "channels": ["panel"], "recipient_ids": [self.advisor_user.pk]},
            ).status_code,
            403,
        )

    def test_profile_reports_and_exports(self):
        self.login(self.student_user)
        profile = self.client.get("/api/profile/")
        self.assertEqual(profile.status_code, 200)
        updated = self.client.patch(
            "/api/profile/",
            {"first_name": "نام جدید"},
        )
        self.assertEqual(updated.status_code, 200, updated.content)
        self.student.profile.refresh_from_db()
        self.assertEqual(self.student.profile.first_name, "نام جدید")
        self.assertEqual(self.client.get("/api/reports/summary/").status_code, 403)

        self.login(self.admin_user)
        summary = self.client.get(
            "/api/reports/summary/?start_date=2026-07-01&end_date=2026-07-31"
        )
        self.assertEqual(summary.status_code, 200, summary.content)
        self.assertIn("advisor_performance", summary.json())
        invalid = self.client.get(
            "/api/reports/summary/?start_date=2026-08-01&end_date=2026-07-01"
        )
        self.assertEqual(invalid.status_code, 400)

        csv_response = self.client.get(
            "/api/reports/export/?section=advisor_performance&format=csv"
        )
        self.assertEqual(csv_response.status_code, 200)
        self.assertTrue(csv_response["Content-Type"].startswith("text/csv"))
        xlsx_response = self.client.get(
            "/api/reports/export/?section=advisor_performance&format=xlsx"
        )
        self.assertEqual(xlsx_response.status_code, 200)
        self.assertIn("spreadsheetml", xlsx_response["Content-Type"])
        zip_response = self.client.get("/api/reports/export/?section=all&format=csv")
        self.assertEqual(zip_response.status_code, 200)
        self.assertEqual(zip_response["Content-Type"], "application/zip")
        with zipfile.ZipFile(BytesIO(zip_response.content)) as archive:
            self.assertTrue(any(name.endswith(".csv") for name in archive.namelist()))
