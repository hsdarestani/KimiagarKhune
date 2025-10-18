
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import *
from accounts.models import *
from django.http import JsonResponse, HttpResponseBadRequest
import json, datetime
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Course, Session, Comment
from .serializers import CourseSerializer, SessionSerializer, CommentSerializer
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.db import transaction


@login_required
def dashboard_view(request):
    """
    این ویو فقط صفحه اصلی داشبورد را که با جاوا اسکریپت کار می‌کند،
    به کاربر نمایش می‌دهد.
    """
    user_profile = getattr(request.user, 'profile', None)
    if request.user.is_staff:
        current_role = 'admin'
    else:
        current_role = getattr(user_profile, 'role', 'student')

    advisor_id = None
    student_id = None
    if user_profile and current_role == 'advisor':
        advisor_id = Advisor.objects.filter(profile=user_profile).values_list('id', flat=True).first()
    if user_profile and current_role == 'student':
        student_id = Student.objects.filter(profile=user_profile).values_list('id', flat=True).first()

    dashboard_user_context = json.dumps({
        'id': request.user.id,
        'username': request.user.username,
        'isStaff': request.user.is_staff,
        'role': current_role,
        'advisorId': advisor_id,
        'studentId': student_id,
    })

    return render(request, 'plans/management.html', {
        'dashboard_user_context': dashboard_user_context,
    })


@login_required
def get_admin_panel_data(request):
    """
    یک API برای واکشی لیست تمام دانش‌آموزان، مشاوران، رشته‌ها و پایه‌ها
    تا در فرم‌های پنل مدیریت استفاده شود.
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    students = Student.objects.select_related('profile').all()
    advisors = Advisor.objects.select_related('profile').all()
    majors = Major.objects.all()
    grades = Grade.objects.all()

    students_data = [{
        'id': s.id,
        'name': f"{s.profile.first_name} {s.profile.last_name}",
        'phone_number': s.profile.phone_number,
        'telegram_chat_id': getattr(s.profile, 'telegram_chat_id', ''),
    } for s in students]
    advisors_data = [{
        'id': a.id,
        'name': f"{a.profile.first_name} {a.profile.last_name}",
        'phone_number': a.profile.phone_number,
        'telegram_chat_id': getattr(a.profile, 'telegram_chat_id', ''),
    } for a in advisors]
    majors_data = [{'id': m.id, 'name': m.name} for m in majors]
    grades_data = [{'id': g.id, 'name': g.name} for g in grades]

    return JsonResponse({
        'students': students_data,
        'advisors': advisors_data,
        'majors': majors_data,
        'grades': grades_data,
    })


@require_POST
@login_required
@transaction.atomic
def add_student_view(request):
    """
    یک دانش‌آموز جدید بر اساس اطلاعات دریافتی از فرم ایجاد می‌کند.
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body)
        
        required_fields = ['first_name', 'last_name', 'phone_number', 'major_id', 'grade_id']
        if not all(field in data for field in required_fields):
            return HttpResponseBadRequest('Missing required fields')

        if User.objects.filter(username=data['phone_number']).exists():
            return HttpResponseBadRequest('A user with this phone number already exists.')

        user = User.objects.create_user(
            username=data['phone_number'],
            password=User.objects.make_random_password()
        )
        
        profile = Profile.objects.create(
            user=user,
            role='student',
            first_name=data['first_name'],
            last_name=data['last_name'],
            phone_number=data['phone_number']
        )
        
        major = Major.objects.get(pk=data['major_id'])
        grade = Grade.objects.get(pk=data['grade_id'])
        school, _ = School.objects.get_or_create(name="مدرسه پیش‌فرض")

        Student.objects.create(
            profile=profile,
            major=major,
            grade=grade,
            school=school
        )
        
        return JsonResponse({'status': 'success', 'message': 'دانش‌آموز با موفقیت ایجاد شد.'}, status=201)

    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON.')
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_POST
@login_required
@transaction.atomic
def assign_student_view(request):
    """
    یک دانش‌آموز را به یک مشاور تخصیص می‌دهد و یک دوره جدید با ۴ جلسه ایجاد می‌کند.
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body)
        student_id = data['student_id']
        advisor_id = data['advisor_id']
        day_of_week = data['day_of_week'] # e.g., 'Saturday'
        start_time_str = data['start_time'] # e.g., '10:00'
        start_date_str = data['start_date'] # e.g., '2024-01-20'

        student = Student.objects.get(pk=student_id)
        advisor = Advisor.objects.get(pk=advisor_id)
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        start_time = datetime.datetime.strptime(start_time_str, '%H:%M').time()

        course = Course.objects.create(
            student=student,
            advisor=advisor,
            day_of_week=day_of_week,
            start_time=start_time,
            start_date=start_date
        )

        session_date = start_date
        for i in range(1, 5):
            Session.objects.create(
                course=course,
                session_number=i,
                date=session_date
            )
            session_date += datetime.timedelta(days=7)
        
        return JsonResponse({'status': 'success', 'message': 'دانش‌آموز با موفقیت تخصیص داده شد.'}, status=201)

    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON.')
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def append_report_log(report, action, additional_data=None, *, user=None):
    logs = report.logs if report.logs else []
    log_entry = {
        "timestamp": timezone.now().isoformat(),
        "action": action,
        "additional_data": additional_data,
    }
    if user is not None:
        log_entry["user"] = {
            "id": user.id,
            "username": user.username,
        }
    logs.append(log_entry)
    report.logs = logs
    report.save(update_fields=["logs"])


@require_POST
@login_required
def log_weekly_report_action(request):
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON.')

    report_id = payload.get('report_id')
    action = payload.get('action')
    additional_data = payload.get('additional_data')

    if not report_id or not action:
        return HttpResponseBadRequest('Missing required fields.')

    try:
        report = WeeklyReport.objects.select_related('student__profile', 'student__advisor__profile').get(pk=report_id)
    except WeeklyReport.DoesNotExist:
        return HttpResponseBadRequest('Report not found.')

    if not request.user.is_staff:
        allowed_users = {report.student.profile.user_id}
        if report.student.advisor and report.student.advisor.profile:
            allowed_users.add(report.student.advisor.profile.user_id)
        if request.user.id not in allowed_users:
            return JsonResponse({'error': 'Permission denied'}, status=403)

    append_report_log(report, action, additional_data, user=request.user)
    return JsonResponse({'status': 'success'})


class IsOwnerOrAdminOrAdvisor(permissions.BasePermission):
    """
    اجازه دسترسی به صاحب رکورد، مشاور مربوطه یا ادمین.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        # For Course object
        if isinstance(obj, Course):
            return obj.student.profile.user == request.user or obj.advisor.profile.user == request.user
        # For Session or Comment, check based on the parent course
        return obj.course.student.profile.user == request.user or obj.course.advisor.profile.user == request.user

class CourseViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Courses.
    """
    queryset = Course.objects.select_related('student__profile', 'advisor__profile').prefetch_related('sessions', 'comments__author__profile').all()
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdminOrAdvisor]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        
        # Filter based on user's role
        if hasattr(user, 'profile'):
            if user.profile.role == 'student':
                return super().get_queryset().filter(student__profile__user=user)
            if user.profile.role == 'advisor':
                return super().get_queryset().filter(advisor__profile__user=user)
        return Course.objects.none()

    @action(detail=True, methods=['post'], url_path='add-comment')
    def add_comment(self, request, pk=None):
        course = self.get_object()
        serializer = CommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(course=course, author=request.user)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    def perform_update(self, serializer):
        user = self.request.user
        role = getattr(getattr(user, 'profile', None), 'role', None)
        if not user.is_staff and role != 'advisor':
            raise PermissionDenied('شما اجازه ویرایش این دوره را ندارید.')
        serializer.save()

class SessionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing individual sessions within a course.
    """
    queryset = Session.objects.all()
    serializer_class = SessionSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdminOrAdvisor]




WEEKDAYS = ['شنبه','یکشنبه','دوشنبه','سه‌شنبه','چهارشنبه','پنج‌شنبه','جمعه']

MAJOR_TO_CODE = {
    "تجربی": "T",
    "ریاضی": "R",
    "انسانی": "E",
}

@login_required
def get_last_weekly_report(request):
    """
    Returns the most recent saved weekly report for a given student,
    serialized as JSON with fields needed by the front-end:
      - lesson_id
      - lesson_name
      - chapter_id
      - chapter_text
      - optional_tests_count
      - duration_minutes
      - grade_id
      - lesson_type
    """
    student_id = request.GET.get('student_id')
    if not student_id:
        return HttpResponseBadRequest("Missing parameter: student_id")

    try:
        student = Student.objects.get(pk=student_id)
    except Student.DoesNotExist:
        return HttpResponseBadRequest("Student not found")

    # Get the latest weekly report for that student
    report = WeeklyReport.objects.filter(student=student) \
                                 .order_by('-week_start') \
                                 .first()
    if not report:
        return JsonResponse({'tasks': []})

    # Only include tasks that came from a lesson (i.e., box.lesson is not None)
    details = WeeklyReportDetail.objects.filter(
        report=report,
        box__lesson__isnull=False
    )

    tasks = []
    for detail in details:
        box = detail.box
        lesson = box.lesson
        chapter = box.chapter
        idx = detail.start_time.weekday()
        tasks.append({
            'lesson_id': lesson.id,
            'lesson_name': lesson.name,
            'chapter_id': chapter.id if chapter else None,
            'chapter_text': chapter.name if chapter else '',
            'optional_tests_count': box.optional_tests_count,
            'duration_minutes': box.duration_minutes,
            'grade_id': lesson.grade.id if lesson.grade else None,
            'lesson_type': lesson.lesson_type.name if lesson.lesson_type else '',
            'grade': lesson.grade.id if lesson.grade else None, 
            'day_of_week': WEEKDAYS[idx]
        })

    return JsonResponse({'tasks': tasks})
def check_weekly_report(request):
    selected_date_str = request.GET.get("selected_date")
    student_id = request.GET.get("student_id")
    
    if not selected_date_str or not student_id:
        return HttpResponseBadRequest("Missing parameters.")
    
    try:
        # Parse the selected date string into a date object.
        selected_date = datetime.datetime.strptime(selected_date_str, "%Y-%m-%d").date()
    except ValueError:
        return HttpResponseBadRequest("Invalid date format. Expected 'YYYY-MM-DD'.")
    
    try:
        student = Student.objects.get(pk=student_id)
    except Student.DoesNotExist:
        return HttpResponseBadRequest("Student not found.")
    
    # Look for a report whose period covers the selected date.
    report = WeeklyReport.objects.filter(
        student=student,
        week_start__lte=selected_date,
        week_end__gte=selected_date
    ).first()
    
    if report:
        return JsonResponse({
            "exists": "current",
            "week_start": report.week_start.isoformat(),
            "week_end": report.week_end.isoformat()
        })
    else:
        # Look for a future report for this student, ordered by week_start.
        future_report = WeeklyReport.objects.filter(
            student=student,
            week_start__gt=selected_date
        ).order_by('week_start').first()
        if future_report:
            return JsonResponse({
                "exists": "future",
                "week_start": future_report.week_start.isoformat(),
                "week_end": future_report.week_end.isoformat()
            })
        else:
            return JsonResponse({
                "exists": False
            })


@login_required
def get_reports_summary(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    try:
        limit = int(request.GET.get('limit', 50))
    except (TypeError, ValueError):
        limit = 50

    reports = (
        WeeklyReport.objects.select_related(
            'student__profile',
            'student__advisor__profile',
        )
        .prefetch_related('details__box')
        .order_by('-week_start')[:limit]
    )

    results = []
    for report in reports:
        details = list(report.details.select_related('box'))
        tasks_count = len(details)
        total_minutes = sum(
            (detail.box.duration_minutes or 0)
            for detail in details
            if detail.box and detail.box.duration_minutes
        )
        results.append({
            'id': report.id,
            'student_name': report.student.profile.get_full_name(),
            'advisor_name': report.student.advisor.profile.get_full_name() if report.student.advisor else '',
            'week_start': report.week_start.isoformat(),
            'week_end': report.week_end.isoformat(),
            'tasks_count': tasks_count,
            'total_minutes': total_minutes,
            'logs_count': len(report.logs or []),
            'important_events': report.important_events or '',
        })

    return JsonResponse({'reports': results})


def get_weekly_report_details(request):
    week_start = request.GET.get("week_start")
    student_id = request.GET.get("student_id")
    
    if not week_start or not student_id:
        return HttpResponseBadRequest("Missing parameters")
    
    try:
        report = WeeklyReport.objects.get(week_start=week_start, student_id=student_id)
        append_report_log(report, "Load Weekly Report", {"week_start": week_start, "student_id": student_id}, user=request.user)
        
        details = WeeklyReportDetail.objects.filter(report=report)
        saved_tasks = []
        for task in details:
            saved_tasks.append({
                "box_type": task.box.box_type.name,
                "title": task.box.name,
                # Include both chapter name and id for proper prepopulation.
                "chapter": task.box.chapter.name if task.box.chapter else "",
                "chapter_id": task.box.chapter.id if task.box.chapter else None,
                "chapter_text": task.box.chapter.name if task.box.chapter else "",
                "optional_tests_count": task.box.optional_tests_count,
                # For convenience, set extra to the same as optional_tests_count.
                "extra": task.box.optional_tests_count,
                "lesson_type": task.box.lesson.lesson_type.name if task.box.lesson else "",
                "lesson_id": task.box.lesson.id if task.box.lesson else None,
                "lesson_name": task.box.lesson.name if task.box.lesson else None,
                "grade": task.box.lesson.grade.id if task.box.lesson else None,
                "start_time": task.start_time.isoformat(),
                "end_time": task.end_time.isoformat(),
                "date": task.start_time.date().isoformat(),
                "day_of_week": task.day_of_week
            })

        important_events = report.important_events or ""
    except WeeklyReport.DoesNotExist:
        saved_tasks = []
        important_events = ""
    
    return JsonResponse({
        "important_events": important_events,
        "tasks": saved_tasks,
    })

# ترتیب دروس اختصاصی برای هر رشته
MAJOR_SUBJECTS = {
    'تجربی':  ["زیست", "ریاضی", "شیمی", "فیزیک", "زمین"],
    'ریاضی':  ["حسابان","ریاضی","آمار", "شیمی", "گسسته", "فیزیک", "هندسه"],
    'انسانی': ["جامعه شناسی", "فلسفه", "ریاضی","آمار", "روانشناسی", "اقتصاد", "علوم و فنون", "منطق", "تاریخ", "جغرافیا"],
}

# ترتیب دروس عمومی
GENERAL_SUBJECTS = ["ادبیات", "عربی", "دینی", "زبان"] 

# ترتیب پایه‌ها: مثلاً اول دوازدهم، بعد دهم، بعد یازدهم
GRADE_ORDER = {
    "دوازدهم": 0,
    "دهم": 1,
    "یازدهم": 2,
}


def get_chapters(request):
    lesson_id  = request.GET.get("lesson_id")
    grade      = request.GET.get("grade")
    major_code = request.GET.get("major_code", "")

    # ۱) واکشی اولیه
    qs = Chapter.objects.filter(
        lesson_id=lesson_id,
        lesson__grade=grade
    )
    # اگر major_code دارید، فیلترش کنید
    if major_code:
        qs = qs.filter(track__icontains=major_code)

    # مرتب‌سازی بر اساس شماره فصل
    qs = qs.order_by("chapter_number")

    # ۲) حذف تکراری‌ها در پایتون
    seen = set()
    chapter_list = []
    for chap in qs:
        key = (chap.chapter_number, chap.name)
        if key in seen:
            continue
        seen.add(key)
        chapter_list.append({
            "id":   chap.id,
            "text": f"{chap.chapter_number} - {chap.name}"
        })

    return JsonResponse(chapter_list, safe=False)
 
@login_required
def plan_view(request):

    advisor = Advisor.objects.filter(profile=request.user.profile).first()
    students = Student.objects.filter(advisor=advisor) if advisor else Student.objects.none()

    firststudent = students.first()
    if firststudent:
        lessons_dict = sort_lessons_for_student(firststudent)
        student_major_code = MAJOR_TO_CODE.get(firststudent.major.name, "")
    else:
        lessons_dict = {'specialized_lessons': [], 'general_lessons': []}
        student_major_code = ""
    return render(request, 'plans/plan.html', {
        'students': students,
        'specialized_lessons': lessons_dict.get('specialized_lessons', []),
        'general_lessons': lessons_dict.get('general_lessons', []),
        'major_code':         student_major_code,
    })


def sort_lessons_for_student(student):
    """
    تمام دروس را واکشی کرده و بر اساس رشته و پایه دانش‌آموز مرتب می‌کند.
    خروجی: لیست مرتب‌شده از اشیای Lesson
    """
    user_major = student.major.name  # مثلاً 'تجربی'، 'ریاضی' یا 'انسانی'
    lessons = Lesson.objects.all()

    # تفکیک درس‌های اختصاصی و عمومی
    major_lessons = []
    general_lessons = []

    # ممکن است رشته‌ای که در دیتابیس دارید، دقیقاً با کلیدهای MAJOR_SUBJECTS فرق داشته باشد
    # پس بهتر است بررسی کنید:
    major_list = MAJOR_SUBJECTS.get(user_major, [])

    for lesson in lessons:
        maj = Chapter.objects.filter(lesson=lesson).first().track
        if "T" in maj:
            lmaj= "تجربی"
        elif "R" in maj:
            lmaj="ریاضی"
        elif "E" in maj:
            lmaj="انسانی"
            
        if lesson.name in major_list:
            major_lessons.append(lesson)
        elif user_major == lmaj:
            general_lessons.append(lesson)
        else:
            pass

    # تعریف کلید مرتب‌سازی برای دروس اختصاصی
    def major_sort_key(lesson):
        # ایندکس نام درس در لیست اختصاصی
        try:
            subject_idx = major_list.index(lesson.name)
        except ValueError:
            subject_idx = 999
        # ایندکس پایه از دیکشنری
        grade_idx = GRADE_ORDER.get(lesson.grade.name, 999)
        return (subject_idx, grade_idx)

    # تعریف کلید مرتب‌سازی برای دروس عمومی
    def general_sort_key(lesson):
        try:
            subject_idx = GENERAL_SUBJECTS.index(lesson.name)
        except ValueError:
            subject_idx = 999
        grade_idx = GRADE_ORDER.get(lesson.grade.name, 999)
        return (subject_idx, grade_idx)

    # مرتب‌سازی
    major_lessons.sort(key=major_sort_key)
    general_lessons.sort(key=general_sort_key)
    return {
        'specialized_lessons': major_lessons,
        'general_lessons': general_lessons,
    }

    
@login_required
def move_lesson_to_end(request):
    if request.method == "POST":
        lesson_id = request.POST.get('lesson_id')
        student_id = request.POST.get('student_id')
        if not lesson_id:
            return JsonResponse({'error': 'Missing lesson_id'}, status=400)
        lesson_id = int(lesson_id)
        student = Student.objects.get(pk=student_id)

        # Get sorted lessons as a dictionary
        lessons_dict = sort_lessons_for_student(student)
        specialized_lessons = lessons_dict.get('specialized_lessons', [])
        general_lessons = lessons_dict.get('general_lessons', [])

        # Look for the selected lesson by ID
        selected_lesson = None
        for ls in specialized_lessons:
            if ls.id == lesson_id:
                selected_lesson = ls
                break
        if not selected_lesson:
            for ls in general_lessons:
                if ls.id == lesson_id:
                    selected_lesson = ls
                    break

        # If the lesson is found, remove it and append it to the end of its list.
        if selected_lesson:
            if selected_lesson in specialized_lessons:
                specialized_lessons.remove(selected_lesson)
                specialized_lessons.append(selected_lesson)
            elif selected_lesson in general_lessons:
                general_lessons.remove(selected_lesson)
                general_lessons.append(selected_lesson)

        # Return the updated order as JSON.
        data = {
            'specialized': [
                {'id': l.id, 'name': l.name, 'grade': l.grade.__str__(), 'grade_id': l.grade.id}
                for l in specialized_lessons
            ],
            'general': [
                {'id': l.id, 'name': l.name, 'grade': l.grade.__str__(), 'grade_id': l.grade.id}
                for l in general_lessons
            ],
        }
        return JsonResponse(data, safe=False)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)
@login_required
def update_lesson_order(request):
    if request.method == "POST":
        import json
        student_id = request.POST.get('student_id')
        specialized_order = json.loads(request.POST.get('specialized_order', '[]'))
        general_order = json.loads(request.POST.get('general_order', '[]'))
        
        # Here you have the new ordering as arrays of lesson IDs.
        # You can now update your database if needed (for example, store the order in the student’s profile)
        # or simply return the new order as confirmation.
        data = {
            'specialized': specialized_order,
            'general': general_order,
        }
        return JsonResponse(data)
    return JsonResponse({'error': 'Invalid request'}, status=400)
@csrf_exempt
@login_required
def save_weekly_report(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            student_id = data.get('student_id')
            week_start_str = data.get('week_start')  # ISO string, e.g., "2025-03-02T00:00:00"
            week_end_str = data.get('week_end')
            days = data.get('days', [])
            important_events = data.get('important_events', "")
            # Parse week start and end datetimes
            week_start = datetime.datetime.fromisoformat(week_start_str)
            week_end = datetime.datetime.fromisoformat(week_end_str)

            # Get the student instance
            student = Student.objects.get(pk=student_id)

            # Build a comma-separated string of disabled day names
            disabled_days = ",".join([day['day'] for day in days if day.get('disabled')])

            # Try to retrieve an existing WeeklyReport for this student and week_start.
            # If one exists, update it; otherwise, create a new report.
            report, created = WeeklyReport.objects.get_or_create(
                student=student,
                week_start=week_start,
                defaults={
                    "week_end": week_end,
                    "disabled_days": disabled_days,
                    "important_events": important_events,
                    "logs": [{
                        "timestamp": timezone.now().isoformat(),
                        "action": "Report created",
                        "user": {
                            "id": request.user.id,
                            "username": request.user.username
                        },
                        "data": {
                            "student_id": student_id,
                            "week_start": week_start_str,
                            "week_end": week_end_str
                        }
                    }]
                }
            )

            if not created:
                # If a report already exists, update its fields and log the update.
                report.week_end = week_end
                report.disabled_days = disabled_days
                report.important_events = important_events
                append_report_log(report, "Report updated", {"week_start": week_start_str, "week_end": week_end_str}, user=request.user)
                # Optionally, remove previous details so that the new ones take full effect:
                report.details.all().delete()
                report.save(update_fields=["week_end", "disabled_days", "logs"])

            # Mapping for day name offsets relative to week_start
            weekday_offset = {
                "شنبه": 0,
                "یکشنبه": 1,
                "دوشنبه": 2,
                "سه‌شنبه": 3,
                "چهارشنبه": 4,
                "پنج‌شنبه": 5,
                "جمعه": 6,
            }

            # For each day, create (new) WeeklyReportDetail records for each task.
            for day in days:
                day_name = day.get('day')
                is_day_disabled = day.get('disabled', False)
                tasks = day.get('tasks', [])
                offset = weekday_offset.get(day_name, 0)
                box_date = (week_start + datetime.timedelta(days=offset)).date()

                for task in tasks:
                    # Expect time-only strings, e.g. "01:30:00"
                    start_time_str = task.get('start')
                    end_time_str = task.get('end')

                    # Parse time-only strings into time objects.
                    start_time_obj = datetime.datetime.strptime(start_time_str, '%H:%M:%S').time()
                    end_time_obj = datetime.datetime.strptime(end_time_str, '%H:%M:%S').time()

                    # Combine the calculated box_date with the time objects.
                    start_datetime = datetime.datetime.combine(box_date, start_time_obj)
                    end_datetime = datetime.datetime.combine(box_date, end_time_obj)

                    # --- Create a new Box instance using provided front-end fields ---
                    box_type_name = task.get('box_type')
                    lesson_id = task.get('lesson_id')  # May be absent for event boxes
                    chapter_id = task.get('chapter_id')
                    optional_tests_count = task.get('optional_tests_count', 0)
                    duration_minutes = task.get('duration_minutes')
                    name = task.get('title')
                    # Look up the BoxType object.
                    box_type_obj = BoxType.objects.get(name=box_type_name)
                    if box_type_name == "ایونت":
                        # برای ایونت نیازی به درس نداریم
                        lesson_obj = None
                        chapter_obj = None
                        optional_tests_count = 0
                        duration_minutes = 0
                        box_instance = Box.objects.create(
                            box_type=box_type_obj,
                            lesson=lesson_obj,
                            chapter=chapter_obj,
                            optional_tests_count=optional_tests_count,
                            duration_minutes=duration_minutes,
                            name=name,
                            is_default=True   
                        )
                    else:
                        # Retrieve lesson and chapter if provided.
                        lesson_obj = Lesson.objects.get(pk=lesson_id) if lesson_id else None
                        if chapter_id:
                            try:
                                chapter_obj = Chapter.objects.get(pk=chapter_id)
                            except Chapter.DoesNotExist:
                                chapter_obj = None
                        else:
                            chapter_obj = None

                        box_instance = Box.objects.create(
                            box_type=box_type_obj,
                            lesson=lesson_obj,
                            chapter=chapter_obj,
                            optional_tests_count=optional_tests_count,
                            duration_minutes=duration_minutes,
                            name=name
                        )

                    # Create the WeeklyReportDetail record.
                    WeeklyReportDetail.objects.create(
                        report=report,
                        box=box_instance,
                        start_time=start_datetime,
                        end_time=end_datetime,
                        day_of_week=day_name,
                        is_disabled=is_day_disabled
                    )
            # Append a final log entry.
            append_report_log(report, "Report details saved", {"days_count": len(days)}, user=request.user)
            report.save(update_fields=["logs"])

            return JsonResponse({"status": "success"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
    else:
        return JsonResponse({"status": "error", "message": "Only POST method allowed."}, status=405)

@csrf_exempt
@login_required
def copy_day_plan(request):
    """
    Expects a POST request with:
     - source_student_id
     - target_student_id
     - source_date (format: "YYYY-MM-DD")
     - target_day_of_week (e.g., "شنبه", "یکشنبه", etc.)

    This view copies all the WeeklyReportDetail records from the source student's report,
    corresponding to the day derived from source_date, into the target student's report
    with the day_of_week field set to the provided target_day_of_week.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed."}, status=405)

    source_student_id = request.POST.get("source_student_id")
    target_student_id = request.POST.get("target_student_id")
    source_date_str = request.POST.get("source_date")
    target_day_of_week = request.POST.get("target_day_of_week")

    if not (source_student_id and target_student_id and source_date_str and target_day_of_week):
        return JsonResponse({"error": "Missing required parameters."}, status=400)

    try:
        source_date = datetime.datetime.strptime(source_date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Invalid source_date format. Expected YYYY-MM-DD."}, status=400)

    # Verify that the logged-in user is the consultant for both students.
    advisor = Advisor.objects.filter(profile=request.user.profile).first()
    if not advisor:
        return JsonResponse({"error": "Advisor not found."}, status=400)

    source_student = Student.objects.filter(pk=source_student_id, advisor=advisor).first()
    target_student = Student.objects.filter(pk=target_student_id, advisor=advisor).first()

    if not source_student or not target_student:
        return JsonResponse({"error": "One or both students are not assigned to your consultancy."}, status=400)

    # Retrieve the source student's report for the week covering source_date.
    source_report = WeeklyReport.objects.filter(
        student=source_student,
        week_start__lte=source_date,
        week_end__gte=source_date
    ).first()
    if not source_report:
        return JsonResponse({"error": "No report found for the source student for the specified date."}, status=400)

    # Mapping of Python's weekday() to Persian day names.
    # Python: Monday=0, Tuesday=1, ..., Saturday=5, Sunday=6.
    persian_weekday_mapping = {
       5: "شنبه",    # Saturday
       6: "یکشنبه",  # Sunday
       0: "دوشنبه",  # Monday
       1: "سه‌شنبه",  # Tuesday
       2: "چهارشنبه",# Wednesday
       3: "پنج‌شنبه",# Thursday
       4: "جمعه"     # Friday
    }
    source_day_of_week = persian_weekday_mapping[source_date.weekday()]

    # Retrieve all details for the computed source day in the source report.
    source_day_details = WeeklyReportDetail.objects.filter(report=source_report, day_of_week=source_day_of_week)
    if not source_day_details.exists():
        return JsonResponse({"error": "No plan details found for the source date's day in the source report."}, status=400)

    # Retrieve or create the target student's report for the same week as the source report.
    target_report, created = WeeklyReport.objects.get_or_create(
        student=target_student,
        week_start=source_report.week_start,
        defaults={
            "week_end": source_report.week_end,
            "disabled_days": "",
            "important_events": ""
        }
    )

    # Remove any existing details for the target day in the target report.
    WeeklyReportDetail.objects.filter(report=target_report, day_of_week=target_day_of_week).delete()

    new_details = []
    for detail in source_day_details:
        original_box = detail.box
        # Duplicate the box instance.
        new_box = Box.objects.create(
            box_type=original_box.box_type,
            lesson=original_box.lesson,
            chapter=original_box.chapter,
            optional_tests_count=original_box.optional_tests_count,
            duration_minutes=original_box.duration_minutes,
            name=original_box.name
        )
        new_detail = WeeklyReportDetail.objects.create(
            report=target_report,
            box=new_box,
            start_time=detail.start_time,  # Optionally adjust time if needed
            end_time=detail.end_time,
            day_of_week=target_day_of_week,  # set to the selected target day
            is_disabled=detail.is_disabled
        )
        new_details.append(new_detail)

    append_report_log(target_report, "Copied day plan", {"source_student_id": source_student.id, "target_day_of_week": target_day_of_week}, user=request.user)
    return JsonResponse({"status": "success", "copied_details_count": len(new_details)})

@login_required
def get_default_events(request):
    student_id = request.GET.get("student_id")
    if not student_id:
        return JsonResponse({"error": "Missing student_id"}, status=400)
    
    try:
        student = Student.objects.get(pk=student_id)
    except Student.DoesNotExist:
        return JsonResponse({"error": "Student not found"}, status=400)
    
    default_details = WeeklyReportDetail.objects.filter(
        report__student=student,
        box__box_type__name="ایونت",
        box__is_default=True
    ).order_by("-report__week_start")  # آخرین گزارش در ابتدا
    
    data = []
    for detail in default_details:
        data.append({
            "name": detail.box.name,
            "day_of_week": detail.day_of_week,
            "start_time": detail.start_time.strftime("%H:%M"),
            "end_time": detail.end_time.strftime("%H:%M"),
            "date": detail.start_time.date().isoformat(),

        })
    return JsonResponse(data, safe=False)

MAJOR_SUBJECTS = {
    'تجربی': ["زیست", "ریاضی", "شیمی", "فیزیک", "زمین"],
    'ریاضی': ["حسابان", "شیمی", "گسسته", "فیزیک", "هندسه"],
    'انسانی': ["جامعه شناسی", "فلسفه", "ریاضی","آمار", "روانشناسی", "اقتصاد", "علوم و فنون", "منطق", "تاریخ", "جغرافیا"],
}
# Note: The ordering here reflects your intended order,
# with a lower number meaning a “higher” grade.
GRADE_ORDER = {
    "دوازدهم": 0,
    "یازدهم": 1,
    "دهم": 2,
}
# Map major names to track codes.
MAJOR_TO_CODE = {
    "تجربی": "T",
    "ریاضی": "R",
    "انسانی": "E"
}

def get_lessons_for_student(request):
    student_id = request.GET.get("student_id")
    if not student_id:
        return HttpResponseBadRequest("Missing student_id parameter.")
    
    try:
        student = Student.objects.get(pk=student_id)
    except Student.DoesNotExist:
        return HttpResponseBadRequest("Student not found.")
    
    # Ensure student has a major and a grade
    if not (hasattr(student, 'major') and student.major and hasattr(student, 'grade') and student.grade):
        return HttpResponseBadRequest("Student major or grade not defined.")

    student_major = student.major.name  # e.g., 'تجربی', 'ریاضی', or 'انسانی'
    student_grade_name = student.grade.name  # e.g., 'دوازدهم', 'دهم', or 'یازدهم'
    # Get the code for the student's major.
    student_major_code = MAJOR_TO_CODE.get(student_major)
    if not student_major_code:
        return HttpResponseBadRequest("Unknown student major.")
    student_major = student.major.name  # مثلاً 'تجربی'
    # محاسبه‌ی کد
    major_code = MAJOR_TO_CODE.get(student_major, "")
    # Fetch all lessons.
    lessons = Lesson.objects.all()
    specialized_lessons = []
    general_lessons = []
    # Get the list of specialized lesson names for this major.
    major_list = MAJOR_SUBJECTS.get(student_major, [])

    for lesson in lessons:
        # Only consider lessons that have an associated grade.
        if not lesson.grade:
            continue
        # Check the grade ordering:
        # Only include if the lesson's grade is "lower or the same" as the student's grade.
        # (Assuming that a higher order number means a lower academic level.)
        lesson_grade_order = GRADE_ORDER.get(lesson.grade.name, 999)
        student_grade_order = GRADE_ORDER.get(student_grade_name, 999)
        #if lesson_grade_order < student_grade_order:
            # This lesson is for a higher grade than the student—skip it.
        #    continue

        # Check track information: get the track string from the first Chapter of this lesson.
        chapter = Chapter.objects.filter(lesson=lesson).first()
        track_str = chapter.track if chapter and chapter.track else ""
        # Split by comma and trim each code.
        track_codes = [code.strip() for code in track_str.split(",") if code.strip()]
        # Only include the lesson if the student's major code is in the lesson's track codes.
        if not Chapter.objects.filter(
                lesson=lesson,
                track__icontains=student_major_code  # دقت کن که E دقیقاً match شود یا regex بزن
            ).exists():
            continue

        # Now, separate lessons:
        # If the lesson's name is in the specialized list (major_list), consider it specialized.
        if lesson.name in major_list:
            specialized_lessons.append(lesson)
        else:
            # Otherwise, include it as general.
            general_lessons.append(lesson)

    # Serialize the lessons for the JSON response.
    specialized_data = [{
        "id": lesson.id,
        "name": lesson.name,
        "grade_id": lesson.grade.id if lesson.grade else None,
        "grade": str(lesson.grade) if lesson.grade else ""
    } for lesson in specialized_lessons]

    general_data = [{
        "id": lesson.id,
        "name": lesson.name,
        "grade_id": lesson.grade.id if lesson.grade else None,
        "grade": str(lesson.grade) if lesson.grade else ""
    } for lesson in general_lessons]

    return JsonResponse({
        "major_code": major_code,
        "specialized_lessons": specialized_data,
        "general_lessons": general_data,
    })

