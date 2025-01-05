from django.db import models

class LessonType(models.Model):
    name = models.CharField(max_length=100)  

    def __str__(self):
        return self.name

class Lesson(models.Model):
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

    def __str__(self):
        return f"Chapter {self.chapter_number}: {self.name}"


class BoxType(models.Model):
    name = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)  

    def __str__(self):
        return self.name

class Box(models.Model):
    box_type = models.ForeignKey(BoxType, on_delete=models.CASCADE)
    lesson = models.ForeignKey('Lesson', on_delete=models.CASCADE)  
    chapter = models.ForeignKey('Chapter', on_delete=models.CASCADE, null=True, blank=True)  
    optional_tests_count = models.IntegerField(default=0)  
    duration_minutes = models.IntegerField()  

    def __str__(self):
        return f"{self.lesson.name} - {self.box_type.name}"
    

class WeeklyReport(models.Model):
    student = models.ForeignKey('accounts.Student', on_delete=models.CASCADE) 
    week_start = models.DateTimeField()  
    week_end = models.DateTimeField()  

    def __str__(self):
        return f"Weekly Report for {self.student.profile.first_name} {self.student.profile.last_name} ({self.week_start} - {self.week_end})"

class WeeklyReportDetail(models.Model):
    report = models.ForeignKey(WeeklyReport, related_name='details', on_delete=models.CASCADE)  
    box = models.ForeignKey(Box, on_delete=models.CASCADE)  
    start_time = models.DateTimeField()  
    end_time = models.DateTimeField()  
    day_of_week = models.CharField(max_length=20)  
    box_date = models.DateField()

    def __str__(self):
        return f"Box: {self.box.lesson.name} ({self.start_time} - {self.end_time})"
