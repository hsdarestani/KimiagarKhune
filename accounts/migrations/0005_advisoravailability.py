from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_loginotp'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdvisorAvailability',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day_of_week', models.CharField(choices=[('Saturday', 'شنبه'), ('Sunday', 'یکشنبه'), ('Monday', 'دوشنبه'), ('Tuesday', 'سه‌شنبه'), ('Wednesday', 'چهارشنبه'), ('Thursday', 'پنج‌شنبه'), ('Friday', 'جمعه')], max_length=10, verbose_name='روز هفته')),
                ('start_time', models.TimeField(verbose_name='ساعت شروع')),
                ('end_time', models.TimeField(verbose_name='ساعت پایان')),
                ('max_students', models.PositiveSmallIntegerField(default=1, verbose_name='حداکثر دانش‌آموز')),
                ('advisor', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='availabilities', to='accounts.advisor', verbose_name='مشاور')),
            ],
            options={
                'ordering': ['advisor_id', 'day_of_week', 'start_time'],
                'unique_together': {('advisor', 'day_of_week', 'start_time')},
            },
        ),
    ]
