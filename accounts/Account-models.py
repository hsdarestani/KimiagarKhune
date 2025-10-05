from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('advisor', 'Advisor'),
        ('admin', 'Admin'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE) 
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True, verbose_name="عکس پروفایل")

    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.role})'


class School(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name 

class Major(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name
    @property
    def code(self):
        mapping = {
            'تجربی': 'T',
            'ریاضی': 'R',
            'انسانی': 'E',
        }
        return mapping.get(self.name, '')
class Grade(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
class Advisor(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE)  

    def __str__(self):
        return f'{self.profile.first_name} {self.profile.last_name} - Advisor'

class Student(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE) 
    school = models.ForeignKey(School, on_delete=models.CASCADE)  
    major = models.ForeignKey(Major, on_delete=models.CASCADE) 
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)  
    advisor = models.ForeignKey(Advisor, on_delete=models.SET_NULL, null=True, blank=True)  
    def __str__(self):
        return f'{self.profile.first_name} {self.profile.last_name} - {self.major.name}'
    
