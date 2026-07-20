# Generated manually for persistent plan defaults.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('plans', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DefaultEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='عنوان ایونت')),
                ('day_of_week', models.CharField(choices=[('شنبه', 'شنبه'), ('یک‌شنبه', 'یک‌شنبه'), ('دوشنبه', 'دوشنبه'), ('سه‌شنبه', 'سه‌شنبه'), ('چهارشنبه', 'چهارشنبه'), ('پنج‌شنبه', 'پنج‌شنبه'), ('جمعه', 'جمعه')], max_length=20, verbose_name='روز هفته')),
                ('start_time', models.TimeField(verbose_name='ساعت شروع')),
                ('end_time', models.TimeField(verbose_name='ساعت پایان')),
                ('is_active', models.BooleanField(default=True, verbose_name='فعال')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='default_events', to='accounts.student', verbose_name='دانش‌آموز')),
            ],
            options={
                'ordering': ['student_id', 'day_of_week', 'start_time'],
                'unique_together': {('student', 'name', 'day_of_week', 'start_time', 'end_time')},
            },
        ),
    ]
