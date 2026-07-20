from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from accounts.models import Grade, Major, Profile, School, Student
from plans.lesson_catalog import sort_lessons_for_student
from plans.models import Chapter, Lesson, LessonType


class LessonGraphImportTests(TestCase):
    def test_default_graph_is_seeded_and_import_is_idempotent(self):
        self.assertEqual(Grade.objects.filter(name__in=["دهم", "یازدهم", "دوازدهم"]).count(), 3)
        self.assertEqual(Major.objects.filter(name__in=["تجربی", "ریاضی", "انسانی"]).count(), 3)
        self.assertEqual(LessonType.objects.count(), 2)
        self.assertEqual(Lesson.objects.count(), 57)
        self.assertEqual(Chapter.objects.count(), 542)

        call_command("import_lesson_graph", verbosity=0)

        self.assertEqual(Lesson.objects.count(), 57)
        self.assertEqual(Chapter.objects.count(), 542)
        self.assertTrue(Lesson.objects.filter(name="زیست", grade__name="دهم").exists())
        self.assertFalse(Lesson.objects.filter(name="زیست دهم").exists())

    def _student(self, major_name: str, username: str) -> Student:
        user = User.objects.create_user(username=username, password="test-password")
        profile = Profile.objects.create(
            user=user,
            role="student",
            first_name="Test",
            last_name=major_name,
        )
        school, _ = School.objects.get_or_create(name="مدرسه تست")
        return Student.objects.create(
            profile=profile,
            school=school,
            major=Major.objects.get(name=major_name),
            grade=Grade.objects.get(name="دهم"),
        )

    def test_catalog_uses_track_codes_and_csv_lesson_type(self):
        experimental = self._student("تجربی", "experimental")
        human = self._student("انسانی", "human")

        experimental_catalog = sort_lessons_for_student(experimental)
        experimental_specialized = {
            lesson.name for lesson in experimental_catalog["specialized_lessons"]
        }
        experimental_general = {
            lesson.name for lesson in experimental_catalog["general_lessons"]
        }
        self.assertIn("زیست", experimental_specialized)
        self.assertNotIn("فلسفه", experimental_specialized)
        self.assertIn("ادبیات", experimental_general)

        human_catalog = sort_lessons_for_student(human)
        human_specialized = {
            lesson.name for lesson in human_catalog["specialized_lessons"]
        }
        human_general = {lesson.name for lesson in human_catalog["general_lessons"]}
        self.assertIn("فلسفه", human_specialized)
        self.assertIn("عربی", human_specialized)
        self.assertNotIn("زیست", human_specialized)
        self.assertIn("ادبیات", human_general)
