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
    path('append-report-log/', append_report_log, name='append_report_log'),
    path('get_default_events/', get_default_events, name='get_default_events'),
    path('get-lessons-for-student/', get_lessons_for_student , name='get_lessons_for_student'),
    path('get-last-weekly-report/', get_last_weekly_report, name='get_last_weekly_report'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('', include(router.urls)),
]
