import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Student
from plans.default_plan_data import ensure_advisor_for_user, seed_plan_defaults
from plans.models import Box, Chapter, Lesson, LessonType


class PlanStudyOptionsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="plan-study-options", email="plan-study@example.com",
            password="test-password",
        )
        advisor = ensure_advisor_for_user(self.user)
        seed_plan_defaults(advisor=advisor)
        self.student = Student.objects.get(
            profile__user__username="demo_plan_student_t"
        )
        lesson_type, _ = LessonType.objects.get_or_create(name="اختصاصی")
        self.physics = Lesson.objects.create(
            subject_code="STUDY-PHYS-10", name="فیزیک",
            grade=self.student.grade, lesson_type=lesson_type,
        )
        self.chemistry = Lesson.objects.create(
            subject_code="STUDY-CHEM-10", name="شیمی",
            grade=self.student.grade, lesson_type=lesson_type,
        )
        self.movement = Chapter.objects.create(
            lesson=self.physics, chapter_number=1, name="حرکت شناسی",
        )
        self.reactions = Chapter.objects.create(
            lesson=self.chemistry, chapter_number=3, name="واکنش‌ها",
        )
        self.client.force_login(self.user)

    def payload(self, *, mode="test", chapter_id=None, items=None):
        return {
            "student_id": self.student.pk,
            "week_start": "2039-01-01",
            "week_end": "2039-01-07",
            "days": [{
                "day": "شنبه", "disabled": False,
                "tasks": [{
                    "box_type": "مطالعه",
                    "title": "فیزیک دهم",
                    "lesson_id": self.physics.pk,
                    "chapter_id": self.movement.pk,
                    "start": "09:00:00",
                    "end": "10:30:00",
                    "optional_tests_count": 25,
                    "study_mode": mode,
                    "study_items": items if items is not None else [{
                        "lesson_id": self.chemistry.pk,
                        "chapter_id": (
                            self.reactions.pk if chapter_id is None else chapter_id
                        ),
                    }],
                }],
            }],
        }

    def save(self, payload):
        return self.client.post(
            "/save-weekly-report/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_test_only_and_extra_chapter_survive_save_and_reload(self):
        response = self.save(self.payload())
        self.assertEqual(response.status_code, 200, response.content)
        box = Box.objects.get(
            weeklyreportdetail__report_id=response.json()["report_id"]
        )
        self.assertEqual(box.study_mode, "test")
        self.assertEqual(box.optional_tests_count, 25)
        self.assertEqual(len(box.study_items), 1)
        self.assertEqual(box.study_items[0]["lesson_id"], self.chemistry.pk)
        self.assertEqual(box.study_items[0]["grade_id"], self.student.grade_id)
        self.assertIn("واکنش‌ها", box.study_items[0]["chapter_text"])

        loaded = self.client.get("/get-weekly-report-details/", {
            "student_id": self.student.pk,
            "week_start": "2039-01-01",
        })
        self.assertEqual(loaded.status_code, 200, loaded.content)
        task = loaded.json()["tasks"][0]
        self.assertEqual(task["study_mode"], "test")
        self.assertEqual(task["study_items"][0]["chapter_id"], self.reactions.pk)
        self.assertEqual(task["optional_tests_count"], 25)

        reused = self.client.get("/get-last-weekly-report/", {
            "student_id": self.student.pk,
        })
        self.assertEqual(reused.status_code, 200, reused.content)
        self.assertEqual(reused.json()["tasks"][0]["study_mode"], "test")
        self.assertEqual(
            reused.json()["tasks"][0]["study_items"][0]["lesson_id"],
            self.chemistry.pk,
        )

    def test_switch_to_study_mode_without_losing_chapters(self):
        self.assertEqual(self.save(self.payload()).status_code, 200)
        response = self.save(self.payload(mode="study"))
        self.assertEqual(response.status_code, 200, response.content)
        loaded = self.client.get("/get-weekly-report-details/", {
            "student_id": self.student.pk,
            "week_start": "2039-01-01",
        })
        self.assertEqual(loaded.json()["tasks"][0]["study_mode"], "study")
        self.assertEqual(len(loaded.json()["tasks"][0]["study_items"]), 1)

    def test_reject_chapter_from_another_lesson(self):
        response = self.save(self.payload(chapter_id=self.movement.pk))
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("فصل", response.json()["message"])

    def test_default_single_lesson_backward_compatibility(self):
        payload = self.payload()
        task = payload["days"][0]["tasks"][0]
        del task["study_mode"]
        del task["study_items"]
        response = self.save(payload)
        self.assertEqual(response.status_code, 200, response.content)
        loaded = self.client.get("/get-weekly-report-details/", {
            "student_id": self.student.pk,
            "week_start": "2039-01-01",
        })
        self.assertEqual(loaded.json()["tasks"][0]["study_mode"], "study")
        self.assertEqual(loaded.json()["tasks"][0]["study_items"], [])

    def test_reused_block_origin_survives_save_and_reload(self):
        payload = self.payload()
        payload["days"][0]["tasks"][0]["source_detail_id"] = 4321
        response = self.save(payload)
        self.assertEqual(response.status_code, 200, response.content)
        loaded = self.client.get("/get-weekly-report-details/", {
            "student_id": self.student.pk,
            "week_start": "2039-01-01",
        })
        self.assertEqual(loaded.status_code, 200)
        self.assertEqual(loaded.json()["tasks"][0]["source_detail_id"], 4321)
