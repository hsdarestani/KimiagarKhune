from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.db.models import F
from django.utils import timezone

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
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="شناسه تلگرام")

    def get_full_name(self):
        first = self.first_name or ""
        last = self.last_name or ""
        full_name = f"{first} {last}".strip()
        if full_name:
            return full_name
        return self.user.get_username()

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
WEEKDAY_CHOICES = [
    ('Saturday', 'شنبه'),
    ('Sunday', 'یکشنبه'),
    ('Monday', 'دوشنبه'),
    ('Tuesday', 'سه‌شنبه'),
    ('Wednesday', 'چهارشنبه'),
    ('Thursday', 'پنج‌شنبه'),
    ('Friday', 'جمعه'),
]


class Advisor(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.profile.first_name} {self.profile.last_name} - Advisor'


class AdvisorAvailability(models.Model):
    advisor = models.ForeignKey(
        Advisor,
        on_delete=models.CASCADE,
        related_name='availabilities',
        verbose_name='مشاور',
    )
    day_of_week = models.CharField(
        max_length=10,
        choices=WEEKDAY_CHOICES,
        verbose_name='روز هفته',
    )
    start_time = models.TimeField(verbose_name='ساعت شروع')
    end_time = models.TimeField(verbose_name='ساعت پایان')
    max_students = models.PositiveSmallIntegerField(default=1, verbose_name='حداکثر دانش‌آموز')

    class Meta:
        unique_together = ('advisor', 'day_of_week', 'start_time')
        ordering = ['advisor_id', 'day_of_week', 'start_time']

    def __str__(self):
        day_display = dict(WEEKDAY_CHOICES).get(self.day_of_week, self.day_of_week)
        return f"{self.advisor} - {day_display} {self.start_time} تا {self.end_time}"

class Student(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE)
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    major = models.ForeignKey(Major, on_delete=models.CASCADE)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)
    advisor = models.ForeignKey(Advisor, on_delete=models.SET_NULL, null=True, blank=True)
    def __str__(self):
        return f'{self.profile.first_name} {self.profile.last_name} - {self.major.name}'


class LoginOTP(models.Model):
    """One-time passwords that allow users to log in via their phone number."""

    phone_number = models.CharField(max_length=15, db_index=True)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempt_count = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(
                fields=['phone_number'],
                name='accounts_lo_phone_n_97a5e1_idx',
            ),
            models.Index(
                fields=['expires_at'],
                name='accounts_lo_expires_3b86f9_idx',
            ),
        ]
        ordering = ['-created_at']

    def mark_attempt(self):
        type(self).objects.filter(pk=self.pk).update(attempt_count=F('attempt_count') + 1)
        self.refresh_from_db(fields=['attempt_count'])

    def mark_used(self):
        if not self.is_used:
            self.is_used = True
            self.save(update_fields=['is_used'])

    def has_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @classmethod
    def create_for_phone(cls, phone_number: str, code: str, ttl_seconds: int = 300):
        expires_at = timezone.now() + timedelta(seconds=ttl_seconds)
        return cls.objects.create(
            phone_number=phone_number,
            code=code,
            expires_at=expires_at,
        )

    
