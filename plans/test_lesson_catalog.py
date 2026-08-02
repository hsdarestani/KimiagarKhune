from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Advisor, Profile, Student
from plans.default_plan_data import ensure_advisor_for_user, seed_plan_defaults
from plans.lesson_catalog import allowed_grade_names, sort_lessons_for_student
from plans.models import Chapter, Lesson, LessonType


class PlanLessonCatalogRulesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username="lesson-rules-admin",
            email="lesson-rules@example.com",
            password="test-password",
        )
        advisor = ensure_advisor_for_user(self.admin)
        seed_plan_defaults(advisor=advisor)
        self.client.force_login(self.admin)

        self.math_student = Student.objects.select_related("grade", "major").get(
            profile__user__username="demo_plan_student_r"
        )
        self.experimental_student = Student.objects.select_related("grade", "major").get(
            profile__user__username="demo_plan_student_t"
        )

        specialized, _ = LessonType.objects.get_or_create(name="اختصاصی")
        general, _ = LessonType.objects.get_or_create(name="عمومی")
        grades = {
            student.grade.name: student.grade
            for student in Student.objects.select_related("grade").all()
        }

        self.math_tenth = Lesson.objects.create(
            subject_code="RULE-R10",
            name="درس ریاضی پایه قبل",
            lesson_type=specialized,
            grade=grades["دهم"],
        )
        Chapter.objects.create(
            chapter_number=1,
            name="فصل ریاضی دهم",
            lesson=self.math_tenth,
            track="R",
        )

        self.math_eleventh = Lesson.objects.create(
            subject_code="RULE-R11",
            name="درس ریاضی پایه جاری",
            lesson_type=specialized,
            grade=grades["یازدهم"],
        )
        self.math_eleventh_chapter = Chapter.objects.create(
            chapter_number=1,
            name="فصل ریاضی یازدهم",
            lesson=self.math_eleventh,
            track="R",
        )

        self.math_twelfth = Lesson.objects.create(
            subject_code="RULE-R12",
            name="درس ریاضی پایه آینده",
            lesson_type=specialized,
            grade=grades["دوازدهم"],
        )
        Chapter.objects.create(
            chapter_number=1,
            name="فصل ریاضی دوازدهم",
            lesson=self.math_twelfth,
            track="R",
        )

        self.experimental_eleventh = Lesson.objects.create(
            subject_code="RULE-T11",
            name="درس اختصاصی تجربی",
            lesson_type=specialized,
            grade=grades["یازدهم"],
        )
        Chapter.objects.create(
            chapter_number=1,
            name="فصل تجربی یازدهم",
            lesson=self.experimental_eleventh,
            track="T",
        )

        self.math_general = Lesson.objects.create(
            subject_code="RULE-RG11",
            name="درس عمومی ریاضی",
            lesson_type=general,
            grade=grades["یازدهم"],
        )
        Chapter.objects.create(
            chapter_number=1,
            name="فصل عمومی ریاضی",
            lesson=self.math_general,
            track="R",
        )

    def make_advisor(self, username: str) -> tuple[object, Advisor]:
        User = get_user_model()
        user = User.objects.create_user(username=username, password="test-password")
        profile = Profile.objects.create(
            user=user,
            role="advisor",
            first_name="مشاور",
            last_name=username,
            phone_number=f"09{user.pk:09d}"[-11:],
        )
        return user, Advisor.objects.create(profile=profile)

    def test_allowed_grades_include_current_and_completed_lower_grades(self):
        self.assertEqual(
            allowed_grade_names(self.math_student),
            {"دهم", "یازدهم"},
        )
        self.assertEqual(
            allowed_grade_names(self.experimental_student),
            {"دهم", "یازدهم", "دوازدهم"},
        )

    def test_catalog_excludes_future_grade_and_other_major(self):
        catalog = sort_lessons_for_student(self.math_student)
        specialized_ids = {lesson.pk for lesson in catalog["specialized_lessons"]}
        general_ids = {lesson.pk for lesson in catalog["general_lessons"]}

        self.assertIn(self.math_tenth.pk, specialized_ids)
        self.assertIn(self.math_eleventh.pk, specialized_ids)
        self.assertNotIn(self.math_twelfth.pk, specialized_ids)
        self.assertNotIn(self.experimental_eleventh.pk, specialized_ids)
        self.assertIn(self.math_general.pk, general_ids)

    def test_lesson_endpoint_returns_authoritative_grade_toolbar_rules(self):
        response = self.client.get(
            "/get-lessons-for-student/",
            {"student_id": self.math_student.pk},
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()

        self.assertEqual(payload["major_code"], "R")
        self.assertEqual(payload["student_grade"], "یازدهم")
        self.assertEqual(payload["student_grade_id"], self.math_student.grade_id)

        allowed_names = {
            option["name"]
            for option in payload["grade_options"]
            if option["id"] in payload["allowed_grade_ids"]
        }
        self.assertEqual(allowed_names, {"دهم", "یازدهم"})

        returned_ids = {
            lesson["id"]
            for lesson in payload["specialized_lessons"]
            + payload["general_lessons"]
        }
        self.assertIn(self.math_tenth.pk, returned_ids)
        self.assertIn(self.math_eleventh.pk, returned_ids)
        self.assertIn(self.math_general.pk, returned_ids)
        self.assertNotIn(self.math_twelfth.pk, returned_ids)
        self.assertNotIn(self.experimental_eleventh.pk, returned_ids)

    def test_assigned_advisor_loads_chapters_from_student_context(self):
        advisor_user, advisor = self.make_advisor("chapter-advisor")
        self.math_student.advisor = advisor
        self.math_student.save(update_fields=["advisor"])
        self.client.force_login(advisor_user)

        response = self.client.get(
            "/get-chapters/",
            {
                "student_id": self.math_student.pk,
                "lesson_id": self.math_eleventh.pk,
            },
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": self.math_eleventh_chapter.pk,
                    "text": "1 - فصل ریاضی یازدهم",
                }
            ],
        )

    def test_unassigned_advisor_cannot_load_student_chapters(self):
        assigned_user, assigned_advisor = self.make_advisor("assigned-advisor")
        other_user, _other_advisor = self.make_advisor("other-advisor")
        self.math_student.advisor = assigned_advisor
        self.math_student.save(update_fields=["advisor"])
        self.client.force_login(other_user)

        response = self.client.get(
            "/get-chapters/",
            {
                "student_id": self.math_student.pk,
                "lesson_id": self.math_eleventh.pk,
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "دسترسی به این دانش‌آموز مجاز نیست.")

    def test_chapter_endpoint_rejects_other_major_and_future_grade_lessons(self):
        for lesson in (self.experimental_eleventh, self.math_twelfth):
            response = self.client.get(
                "/get-chapters/",
                {
                    "student_id": self.math_student.pk,
                    "lesson_id": lesson.pk,
                },
            )
            self.assertEqual(response.status_code, 403, response.content)
