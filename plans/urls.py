from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import (
    chapter_catalog,
    dashboard_admin,
    dashboard_assignment,
    dashboard_page,
    lesson_catalog,
    plan_page,
    plan_reuse,
    weekly_plans,
    weekly_plans_v2,
)
from .advisor_access import user_can_access_student
from .views import *


# weekly_plans_v2 imports _student_or_response from the legacy weekly_plans
# module. Keep that validator, but make its access decision use the same policy
# as Dashboard, Chat and the Plan lesson endpoints. This compatibility hook can
# be removed once the legacy module is retired.
def _canonical_weekly_student_access(request, student):
    return user_can_access_student(request.user, student)


weekly_plans._can_access_student = _canonical_weekly_student_access


router = DefaultRouter()
router.register(r"courses", CourseViewSet, basename="course")
router.register(r"sessions", SessionViewSet, basename="session")

urlpatterns = [
    path("plan/", plan_page.plan_view, name="plan"),
    path("move-lesson-to-end/", lesson_catalog.move_lesson_to_end, name="move_lesson_to_end"),
    path("get-chapters/", chapter_catalog.get_chapters, name="get-chapters"),
    path("save-weekly-report/", weekly_plans_v2.save_weekly_report, name="save_weekly_report"),
    path("get-weekly-report-details/", weekly_plans_v2.get_weekly_report_details, name="get_weekly_report_details"),
    path("update-lesson-order/", update_lesson_order, name="update_lesson_order"),
    path("check-weekly-report/", weekly_plans_v2.check_weekly_report, name="check_weekly_report"),
    path("copy_day_plan/", weekly_plans_v2.copy_day_plan, name="copy_day_plan"),
    path("get_default_boxes/", lesson_catalog.get_default_boxes, name="get_default_boxes"),
    path("get_default_events/", lesson_catalog.get_default_events, name="get_default_events"),
    path("get-lessons-for-student/", lesson_catalog.get_lessons_for_student, name="get_lessons_for_student"),
    path("get-last-weekly-report/", plan_reuse.get_last_weekly_report, name="get_last_weekly_report"),
    path("dashboard/", dashboard_page.dashboard_view, name="dashboard"),
    path("api/admin-panel-data/", get_admin_panel_data, name="api_admin_panel_data"),
    path("api/add-student/", dashboard_admin.add_student_view, name="api_add_student"),
    path("api/admin/advisors/", dashboard_admin.admin_advisors_view, name="api_admin_advisors"),
    path("api/admin/advisors/<int:advisor_id>/availability/", admin_advisor_add_availability, name="api_admin_advisor_add_availability"),
    path("api/admin/advisors/availability/<int:availability_id>/", admin_advisor_delete_availability, name="api_admin_advisor_delete_availability"),
    path("api/assign-student/", dashboard_assignment.assign_student_view, name="api_assign_student"),
    path("api/log-weekly-report-action/", log_weekly_report_action, name="api_log_weekly_report_action"),
    path("", include(router.urls)),
]
