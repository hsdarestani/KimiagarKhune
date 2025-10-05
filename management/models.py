from django.db import models
from django.contrib.auth.models import User
from accounts.models import Student
from plans.models import Course

class Payment(models.Model):
    """
    مدیریت پرداخت‌های ثبت‌شده توسط دانش‌آموزان.
    """
    STATUS_CHOICES = [
        ('pending', 'در انتظار تایید'),
        ('approved', 'تایید شده'),
        ('rejected', 'رد شده'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments', verbose_name="دانش‌آموز")
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="مربوط به دوره")
    amount = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="مبلغ (تومان)")
    reference_number = models.CharField(max_length=100, verbose_name="شماره پیگیری/ارجاع")
    payment_date = models.DateField(verbose_name="تاریخ واریز")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name="وضعیت")
    created_at = models.DateTimeField(auto_now_add=True)
    admin_notes = models.TextField(blank=True, null=True, verbose_name="یادداشت ادمین")

    def __str__(self):
        return f"پرداختی از {self.student} به مبلغ {self.amount}"

class ChatMessage(models.Model):
    """
    هر پیام در سیستم چت بین دو کاربر.
    """
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages', verbose_name="فرستنده")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages', verbose_name="گیرنده")
    text = models.TextField(blank=True, null=True, verbose_name="متن پیام")
    file = models.FileField(upload_to='chat_files/', blank=True, null=True, verbose_name="فایل")
    voice = models.FileField(upload_to='chat_voices/', blank=True, null=True, verbose_name="پیام صوتی")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="زمان ارسال")
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"پیام از {self.sender} به {self.receiver}"
    
    class Meta:
        ordering = ['timestamp']

