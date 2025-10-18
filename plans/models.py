from django.db import models
from django.contrib.auth.models import User
from accounts.models import Student, Advisor

class Course(models.Model):
    """
    نشان‌دهنده یک دوره مشاوره ۴ جلسه‌ای برای یک دانش‌آموز.
    این کارت اصلی است که در تقویم نمایش داده می‌شود.
    """
    DAY_CHOICES = [
        ('Saturday', 'شنبه'),
        ('Sunday', 'یکشنبه'),
        ('Monday', 'دوشنبه'),
        ('Tuesday', 'سه‌شنبه'),
        ('Wednesday', 'چهارشنبه'),
        ('Thursday', 'پنج‌شنبه'),
        ('Friday', 'جمعه'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='courses', verbose_name="دانش‌آموز")
    advisor = models.ForeignKey(Advisor, on_delete=models.CASCADE, related_name='courses', verbose_name="مشاور")
    day_of_week = models.CharField(max_length=10, choices=DAY_CHOICES, verbose_name="روز هفته")
    start_time = models.TimeField(verbose_name="ساعت شروع")
    start_date = models.DateField(verbose_name="تاریخ شروع دوره")
    is_active = models.BooleanField(default=True, verbose_name="دوره فعال است؟")
    class_link = models.URLField(blank=True, null=True, verbose_name="لینک کلاس")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"دوره {self.student} با {self.advisor} - {self.get_day_of_week_display()} ها"

class Session(models.Model):
    """
    نشان‌دهنده یک جلسه از یک دوره ۴ جلسه‌ای.
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sessions')
    session_number = models.PositiveSmallIntegerField(verbose_name="شماره جلسه") # e.g., 1 to 4
    date = models.DateField(verbose_name="تاریخ جلسه")
    is_completed = models.BooleanField(default=False, verbose_name="تیک خورده؟")
    video_url = models.URLField(blank=True, null=True, verbose_name="لینک فیلم جلسه")
    
    class Meta:
        unique_together = ('course', 'session_number')

    def __str__(self):
        return f"جلسه {self.session_number} از دوره {self.course.id}"

class Comment(models.Model):
    """
    نظراتی که برای هر دوره ثبت می‌شود.
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="نویسنده")
    text = models.TextField(verbose_name="متن نظر")
    attachment = models.FileField(upload_to='comment_attachments/', null=True, blank=True, verbose_name="فایل ضمیمه")
    voice_note = models.FileField(upload_to='comment_voices/', null=True, blank=True, verbose_name="پیام صوتی")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"نظر از {self.author.username} برای دوره {self.course.id}"
        
        
class LessonType(models.Model):
    name = models.CharField(max_length=100)  

    def __str__(self):
        return self.name

class Lesson(models.Model):
    subject_code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)  
    lesson_type = models.ForeignKey('LessonType', on_delete=models.CASCADE)  
    grade = models.ForeignKey('accounts.Grade', on_delete=models.CASCADE)  
    paired_lesson = models.CharField(max_length=255, blank=True, null=True)  

    def __str__(self):
        return self.name

class Chapter(models.Model):
    chapter_number = models.IntegerField() 
    name = models.CharField(max_length=255) 
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)  
    track = models.CharField(max_length=10, blank=True, null=True)
    def __str__(self):
        return f"Chapter {self.chapter_number}: {self.name}"


class BoxType(models.Model):
    name = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)  

    def __str__(self):
        return self.name

class Box(models.Model):
    box_type = models.ForeignKey(BoxType, on_delete=models.CASCADE)
    lesson = models.ForeignKey('Lesson', on_delete=models.CASCADE, null=True, blank=True)  
    chapter = models.ForeignKey('Chapter', on_delete=models.CASCADE, null=True, blank=True)  
    optional_tests_count = models.IntegerField(default=0)  
    duration_minutes = models.IntegerField(null=True, blank=True)  
    name = models.CharField(max_length=100,null=True, blank=True)
    is_default = models.BooleanField(default=False)
    def __str__(self):
        return f"{self.lesson.name} - {self.box_type.name}"
    

class WeeklyReport(models.Model):
    student = models.ForeignKey('accounts.Student', on_delete=models.CASCADE) 
    week_start = models.DateTimeField()  
    week_end = models.DateTimeField()  
    disabled_days = models.CharField(max_length=100, blank=True, null=True)
    logs = models.JSONField(blank=True, null=True, default=list)
    important_events = models.TextField(blank=True, null=True)  
    def __str__(self):
        return f"Weekly Report for {self.student.profile.first_name} {self.student.profile.last_name} ({self.week_start} - {self.week_end})"

class WeeklyReportDetail(models.Model):
    report = models.ForeignKey(WeeklyReport, related_name='details', on_delete=models.CASCADE)  
    box = models.ForeignKey(Box, on_delete=models.CASCADE)  
    start_time = models.DateTimeField()  
    end_time = models.DateTimeField()  
    day_of_week = models.CharField(max_length=20)  
    is_disabled = models.BooleanField(default=False)  

    def __str__(self):
        return f"Box: {self.box.lesson.name} ({self.start_time} - {self.end_time})"
