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

        self.admin_user, _ = self.make_user("dash-admin", "admin", is_staff=True)
        self.advisor_user, advisor_profile = self.make_user("dash-advisor", "advisor")
        self.advisor = Advisor.objects.create(profile=advisor_profile)
        self.other_advisor_user, other_advisor_profile = self.make_user("other-advisor", "advisor")
        self.other_advisor = Advisor.objects.create(profile=other_advisor_profile)

        self.student_user, student_profile = self.make_user("dash-student", "student")
        self.student = Student.objects.create(
            profile=student_profile,
            school=self.school,
            major=self.major,
            grade=self.grade,
            advisor=self.advisor,
        )
        self.other_student_user, other_profile = self.make_user("other-student", "student")
        self.other_student = Student.objects.create(
            profile=other_profile,
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

    def make_user(self, username, role, *, is_staff=False):
        user = User.objects.create_user(
            username=username,
            password="test-password",
            is_staff=is_staff,
        )
        profile = Profile.objects.create(
            user=user,
            role=role,
            first_name=username,
            last_name="تست",
            phone_number=f"09{user.pk:09d}"[-11:],
        )
        return user, profile

    def login(self, user):
        self.client.force_login(user)

    def json_request(self, method, path, payload):
        return getattr(self.client, method)(
            path,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_dashboard_role_context_and_required_components(self):
        self.assertEqual(self.client.get("/dashboard/").status_code, 302)
        for user, role in (
            (self.admin_user, "admin"),
            (self.advisor_user, "advisor"),
            (self.student_user, "student"),
        ):
            self.login(user)
            response = self.client.get("/dashboard/")
            self.assertEqual(response.status_code, 200)
            context = json.loads(response.context["dashboard_user_context"])
            self.assertEqual(context["role"], role)
            self.assertContains(response, 'id="calendar-grid"')
            self.assertContains(response, 'id="chat-toggle-btn"')
            self.assertContains(response, 'id="notifications-btn"')
            self.client.logout()

    def test_admin_account_creation_availability_and_assignment(self):
        self.login(self.student_user)
        self.assertEqual(self.client.get("/api/admin-panel-data/").status_code, 403)
        self.login(self.admin_user)
        self.assertEqual(self.client.get("/api/admin-panel-data/").status_code, 200)

        created_student = self.json_request(
            "post",
            "/api/add-student/",
            {
                "first_name": "جدید",
                "last_name": "دانش‌آموز",
                "phone_number": "09120000001",
                "major_id": self.major.pk,
                "grade_id": self.grade.pk,
            },
        )
        self.assertEqual(created_student.status_code, 201, created_student.content)
        student_user = User.objects.get(username="09120000001")
        self.assertFalse(student_user.has_usable_password())
        new_student = Student.objects.get(profile__user=student_user)

        duplicate = self.json_request(
            "post",
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

        created_advisor = self.json_request(
            "post",
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
        self.assertEqual(created_advisor.status_code, 201, created_advisor.content)
        advisor = Advisor.objects.get(profile__user__username="09120000002")
        self.assertFalse(advisor.profile.user.has_usable_password())
        self.assertEqual(advisor.availabilities.count(), 1)

        assigned = self.json_request(
            "post",
            "/api/assign-student/",
            {
                "student_id": new_student.pk,
                "advisor_id": advisor.pk,
                "day_of_week": "Wednesday",
                "start_time": "14:00",
                "start_date": "2026-07-22",
            },
        )
        self.assertEqual(assigned.status_code, 201, assigned.content)
        course = Course.objects.get(student=new_student, advisor=advisor)
        self.assertEqual(course.sessions.count(), 4)

    def test_course_session_comment_upload_schedule_and_completion(self):
        self.login(self.student_user)
        courses = self.client.get("/courses/")
        self.assertEqual(courses.status_code, 200)
        self.assertEqual({item["id"] for item in courses.json()}, {self.course.pk})
        comment = self.client.post(
            f"/courses/{self.course.pk}/add-comment/", {"text": "نظر تست"}
        )
        self.assertEqual(comment.status_code, 201, comment.content)
        self.assertTrue(Comment.objects.filter(course=self.course, text="نظر تست").exists())
        session = self.course.sessions.get(session_number=1)
        denied_upload = self.client.post(
            f"/sessions/{session.pk}/upload-plan/",
            {"plan_file": SimpleUploadedFile("plan.pdf", b"pdf", content_type="application/pdf")},
        )
        self.assertEqual(denied_upload.status_code, 403)

        self.login(self.advisor_user)
        uploaded = self.client.post(
            f"/sessions/{session.pk}/upload-plan/",
            {"plan_file": SimpleUploadedFile("plan.pdf", b"pdf", content_type="application/pdf")},
        )
        self.assertEqual(uploaded.status_code, 200, uploaded.content)
        denied_schedule = self.json_request(
            "patch",
            f"/courses/{self.course.pk}/",
            {"day_of_week": "Monday", "start_time": "10:00", "start_date": "2026-07-27"},
        )
        self.assertEqual(denied_schedule.status_code, 403)

        self.login(self.admin_user)
        moved = self.json_request(
            "patch",
            f"/courses/{self.course.pk}/",
            {"day_of_week": "Monday", "start_time": "10:00", "start_date": "2026-07-27"},
        )
        self.assertEqual(moved.status_code, 200, moved.content)
        session_dates = list(
            Session.objects.filter(course=self.course)
            .order_by("session_number")
            .values_list("date", flat=True)
        )
        self.assertEqual(
            session_dates,
            [date(2026, 7, 27) + timedelta(days=7 * index) for index in range(4)],
        )

        Session.objects.filter(course=self.course, session_number__lt=4).update(is_completed=True)
        fourth = Session.objects.get(course=self.course, session_number=4)
        self.login(self.advisor_user)
        with patch("plans.views.send_telegram_message"), patch("plans.views.send_sms_message"):
            completed = self.json_request(
                "patch", f"/sessions/{fourth.pk}/", {"is_completed": True}
            )
        self.assertEqual(completed.status_code, 200, completed.content)
        self.course.refresh_from_db()
        self.assertTrue(self.course.payment_notification_sent)
        self.assertTrue(NotificationRecipient.objects.filter(user=self.student_user).exists())

    def test_chat_relationship_security_direct_pair_and_file(self):
        self.login(self.student_user)
        conversations = self.client.get("/api/chat/conversations/")
        self.assertEqual(conversations.status_code, 200)
        conversation_ids = {item["id"] for item in conversations.json()}
        self.assertIn(f"user:{self.advisor_user.pk}", conversation_ids)
        self.assertNotIn(f"user:{self.other_advisor_user.pk}", conversation_ids)

        sent = self.client.post(
            f"/api/chat/messages/user:{self.advisor_user.pk}/", {"text": "سلام"}
        )
        self.assertEqual(sent.status_code, 201, sent.content)
        file_sent = self.client.post(
            f"/api/chat/messages/user:{self.advisor_user.pk}/",
            {"file": SimpleUploadedFile("note.txt", b"hello", content_type="text/plain")},
        )
        self.assertEqual(file_sent.status_code, 201, file_sent.content)
        self.assertTrue(ChatMessage.objects.exclude(file="").filter(file__isnull=False).exists())

        self.assertEqual(
            self.client.get(f"/api/chat/messages/user:{self.other_advisor_user.pk}/").status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                f"/api/chat/messages/user:{self.other_advisor_user.pk}/",
                {"text": "غیرمجاز"},
            ).status_code,
            403,
        )
        pair_path = f"/api/chat/messages/pair:{self.advisor_user.pk}:{self.student_user.pk}/"
        self.assertEqual(self.client.get(pair_path).status_code, 403)
        self.login(self.admin_user)
        self.assertEqual(self.client.get(pair_path).status_code, 200)

    def test_payments_notifications_and_profile(self):
        self.login(self.student_user)
        payment_response = self.json_request(
            "post",
            "/api/payments/submit/",
            {
                "amount": 450000,
                "reference_number": "REF-1",
                "payment_date": "2026-07-22",
                "course": self.course.pk,
            },
        )
        self.assertEqual(payment_response.status_code, 201, payment_response.content)
        payment = Payment.objects.get(reference_number="REF-1")
        self.assertEqual(payment.student, self.student)
        self.assertEqual([item["id"] for item in self.client.get("/api/payments/mine/").json()], [payment.pk])

        profile = self.client.get("/api/profile/")
        self.assertEqual(profile.status_code, 200)
        updated = self.json_request("patch", "/api/profile/", {"first_name": "نام جدید"})
        self.assertEqual(updated.status_code, 200, updated.content)
        self.student.profile.refresh_from_db()
        self.assertEqual(self.student.profile.first_name, "نام جدید")

        self.login(self.admin_user)
        self.assertEqual(self.client.get("/api/payments/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/payments/{payment.pk}/approve/").status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "approved")
        self.assertEqual(
            self.client.post(
                f"/api/payments/{payment.pk}/reject/", {"notes": "نامعتبر"}
            ).status_code,
            200,
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, "rejected")

        notification = self.json_request(
            "post",
            "/api/notifications/send/",
            {
                "message": "اعلان تست",
                "channels": ["panel"],
                "recipient_ids": [self.student_user.pk],
            },
        )
        self.assertEqual(notification.status_code, 201, notification.content)
        self.login(self.student_user)
        inbox = self.client.get("/api/notifications/inbox/")
        self.assertEqual(inbox.status_code, 200)
        recipient_id = inbox.json()[0]["id"]
        marked = self.json_request(
            "post", "/api/notifications/mark-read/", {"ids": [recipient_id]}
        )
        self.assertEqual(marked.json()["updated"], 1)
        self.assertTrue(NotificationRecipient.objects.get(pk=recipient_id).is_read)
        self.assertEqual(
            self.json_request(
                "post",
                "/api/notifications/send/",
                {
                    "message": "غیرمجاز",
                    "channels": ["panel"],
                    "recipient_ids": [self.advisor_user.pk],
                },
            ).status_code,
            403,
        )

    def test_admin_reports_summary_and_exports(self):
        self.login(self.student_user)
        self.assertEqual(self.client.get("/api/reports/summary/").status_code, 403)
        self.login(self.admin_user)
        summary = self.client.get(
            "/api/reports/summary/?start_date=2026-07-01&end_date=2026-07-31"
        )
        self.assertEqual(summary.status_code, 200, summary.content)
        self.assertIn("advisor_performance", summary.json())
        self.assertEqual(
            self.client.get(
                "/api/reports/summary/?start_date=2026-08-01&end_date=2026-07-01"
            ).status_code,
            400,
        )
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
        with zipfile.ZipFile(BytesIO(zip_response.content)) as archive:
            self.assertTrue(any(name.endswith(".csv") for name in archive.namelist()))
