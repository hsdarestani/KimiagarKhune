from django.contrib import admin
from .models import Profile, School, Major, Grade, Student, Advisor

admin.site.register(Profile)
admin.site.register(School)
admin.site.register(Major)
admin.site.register(Grade)
admin.site.register(Student)
admin.site.register(Advisor)
