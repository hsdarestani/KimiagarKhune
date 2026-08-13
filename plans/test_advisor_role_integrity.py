from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Advisor, Profile
from plans.default_plan_data import ensure_advisor_for_user


class AdvisorProfileRoleIntegrityTests(TestCase):
    def _student_profile(self, username: str):
        User = get_user_model()
        user = User.objects.create_user(username=username, password="test-password")
        profile = Profile.objects.create(
            user=user,
            role="student",
            first_name="مشاور",
            last_name="تست",
        )
        return user, profile

    def test_creating_advisor_promotes_student_profile_role(self):
        _user, profile = self._student_profile("advisor-role-create")

        Advisor.objects.create(profile=profile)

        profile.refresh_from_db()
        self.assertEqual(profile.role, "advisor")

    def test_ensure_advisor_repairs_existing_misclassified_profile(self):
        user, profile = self._student_profile("advisor-role-repair")
        advisor = Advisor.objects.create(profile=profile)

        # Simulate a legacy/bad import that changed only Profile.role afterwards.
        Profile.objects.filter(pk=profile.pk).update(role="student")
        profile.refresh_from_db()
        self.assertEqual(profile.role, "student")

        resolved = ensure_advisor_for_user(user)

        profile.refresh_from_db()
        self.assertEqual(resolved.pk, advisor.pk)
        self.assertEqual(profile.role, "advisor")
