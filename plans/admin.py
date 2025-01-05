from django.contrib import admin
from .models import BoxType, Box, WeeklyReport, WeeklyReportDetail, Lesson, Chapter, LessonType

admin.site.register(BoxType)
admin.site.register(Box)
admin.site.register(WeeklyReport)
admin.site.register(WeeklyReportDetail)
admin.site.register(Lesson)
admin.site.register(Chapter)
admin.site.register(LessonType)
