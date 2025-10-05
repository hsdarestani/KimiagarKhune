from django.urls import path, include
from .views import *  
from rest_framework.routers import DefaultRouter


# ساخت یک روتر برای ثبت خودکار URL ها برای ViewSet ها
router = DefaultRouter()
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'sessions', SessionViewSet, basename='session')


urlpatterns = [
    path('plan/', plan_view, name='plan'),
    path('move-lesson-to-end/', move_lesson_to_end, name='move_lesson_to_end'),
    path('get-chapters/', get_chapters, name='get-chapters'),
    path('save-weekly-report/', save_weekly_report, name='save_weekly_report'),
    path('get-weekly-report-details/', get_weekly_report_details, name='get_weekly_report_details'),
    path('update-lesson-order/', update_lesson_order, name='update_lesson_order'),
    path('check-weekly-report/', check_weekly_report, name='check_weekly_report'),
    path('copy_day_plan/', copy_day_plan, name='copy_day_plan'),
    path('get_default_events/', get_default_events, name='get_default_events'),
    path('get-lessons-for-student/', get_lessons_for_student , name='get_lessons_for_student'),
    path('get-last-weekly-report/', get_last_weekly_report, name='get_last_weekly_report'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('api/admin-panel-data/', get_admin_panel_data, name='api_admin_panel_data'),
    path('api/add-student/', add_student_view, name='api_add_student'),
    path('api/assign-student/', assign_student_view, name='api_assign_student'),
    path('api/log-weekly-report-action/', log_weekly_report_action, name='api_log_weekly_report_action'),
    path('api/reports/summary/', get_reports_summary, name='api_reports_summary'),
    path('', include(router.urls)),
]
