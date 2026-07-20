from django.contrib import admin

from .models import (
    Box,
    BoxType,
    Chapter,
    DefaultEvent,
    Lesson,
    LessonType,
    WeeklyReport,
    WeeklyReportDetail,
)


admin.site.register(BoxType)
admin.site.register(Box)
admin.site.register(DefaultEvent)
admin.site.register(WeeklyReport)
admin.site.register(WeeklyReportDetail)
admin.site.register(Lesson)
admin.site.register(Chapter)
admin.site.register(LessonType)
