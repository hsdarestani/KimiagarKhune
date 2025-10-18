import json
import random
import re

from django.contrib.auth import authenticate, get_user_model, login
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.urls import reverse

from management.utils import normalize_phone_number, send_sms_message

from .models import Advisor, LoginOTP, Profile

def advisor_detail(request, advisor_id):
    try:
        advisor = Advisor.objects.get(id=advisor_id)
        students = advisor.student_set.all() 
    except Advisor.DoesNotExist:
        advisor = None
        students = []

    return render(request, 'accounts/advisor_detail.html', {'advisor': advisor, 'students': students})


PASSWORD_ERROR_MESSAGE = "نام کاربری یا رمز عبور نادرست است."
OTP_RESEND_INTERVAL = 60  # seconds
OTP_CODE_TTL = 5 * 60  # seconds
OTP_MAX_ATTEMPTS = 5


def _load_request_data(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return {}
    return request.POST


def _candidate_phone_values(normalized_phone: str):
    digits = re.sub(r'\D', '', normalized_phone or '')
    candidates = {normalized_phone}
    if len(digits) >= 10:
        last_ten = digits[-10:]
        candidates.add(last_ten)
        candidates.add('0' + last_ten)
        candidates.add('+98' + last_ten)
    return list({value for value in candidates if value})


def _get_user_for_phone(normalized_phone: str):
    candidates = _candidate_phone_values(normalized_phone)
    if not candidates:
        return None

    profile = (
        Profile.objects.select_related('user')
        .filter(phone_number__in=candidates)
        .order_by('id')
        .first()
    )
    if profile and profile.user.is_active:
        return profile.user

    UserModel = get_user_model()
    user = (
        UserModel.objects.filter(username__in=candidates)
        .order_by('id')
        .first()
    )
    if user and user.is_active:
        return user
    return None


def login_view(request):
    if request.user.is_authenticated:
        return redirect("plan")
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("plan")  # Change "home" to your desired post-login URL name
        else:
            # You could pass an error message to the template context if needed.
            context = {"error": PASSWORD_ERROR_MESSAGE}
            return render(request, "accounts/login.html", context)
    return render(request, "accounts/login.html")


@require_http_methods(["POST"])
def request_login_otp(request):
    data = _load_request_data(request)
    raw_phone = (data.get('phone_number') or '').strip()
    if not raw_phone:
        return JsonResponse({'detail': 'شماره موبایل الزامی است.'}, status=400)

    normalized = normalize_phone_number(raw_phone)
    if not normalized or len(re.sub(r'\D', '', normalized)) < 10:
        return JsonResponse({'detail': 'شماره موبایل وارد شده معتبر نیست.'}, status=400)

    user = _get_user_for_phone(normalized)
    if not user:
        return JsonResponse({'detail': 'حساب کاربری با این شماره موبایل یافت نشد.'}, status=404)

    now = timezone.now()
    recent = (
        LoginOTP.objects.filter(phone_number=normalized, is_used=False)
        .order_by('-created_at')
        .first()
    )
    if recent and (now - recent.created_at).total_seconds() < OTP_RESEND_INTERVAL:
        retry_after = OTP_RESEND_INTERVAL - int((now - recent.created_at).total_seconds())
        return JsonResponse({
            'detail': 'کد تایید قبلا ارسال شده است. لطفا چند لحظه صبر کنید.',
            'retry_after': max(retry_after, 1),
        }, status=429)

    LoginOTP.objects.filter(phone_number=normalized, expires_at__lt=now).update(is_used=True)

    code = f"{random.randint(100000, 999999)}"
    otp = LoginOTP.create_for_phone(normalized, code, ttl_seconds=OTP_CODE_TTL)
    LoginOTP.objects.filter(phone_number=normalized, is_used=False).exclude(pk=otp.pk).update(is_used=True)

    message = f"کد ورود شما: {code}\nپنل کیمیاگرخونه"
    try:
        send_sms_message(normalized, message)
    except Exception as exc:
        otp.delete()
        return JsonResponse({'detail': str(exc)}, status=400)

    return JsonResponse({'detail': 'کد تایید برای شما ارسال شد.', 'expires_in': OTP_CODE_TTL})


@require_http_methods(["POST"])
def verify_login_otp(request):
    data = _load_request_data(request)
    raw_phone = (data.get('phone_number') or '').strip()
    code = (data.get('code') or '').strip()

    if not raw_phone or not code:
        return JsonResponse({'detail': 'شماره موبایل و کد تایید الزامی است.'}, status=400)

    normalized = normalize_phone_number(raw_phone)

    otp = (
        LoginOTP.objects.filter(phone_number=normalized)
        .order_by('-created_at')
        .first()
    )
    if not otp:
        return JsonResponse({'detail': 'کد تایید نامعتبر است.'}, status=400)

    if otp.is_used or otp.has_expired():
        otp.is_used = True
        otp.save(update_fields=['is_used'])
        return JsonResponse({'detail': 'کد تایید منقضی شده است. لطفا دوباره درخواست دهید.'}, status=400)

    if otp.code != code:
        otp.mark_attempt()
        if otp.attempt_count >= OTP_MAX_ATTEMPTS:
            otp.mark_used()
            return JsonResponse({'detail': 'دفعات تلاش بیش از حد مجاز بود. لطفا دوباره کد دریافت کنید.'}, status=429)
        return JsonResponse({'detail': 'کد تایید وارد شده صحیح نیست.'}, status=400)

    user = _get_user_for_phone(normalized)
    if not user:
        otp.mark_used()
        return JsonResponse({'detail': 'حساب کاربری مرتبط یافت نشد.'}, status=404)

    otp.mark_used()
    login(request, user)
    return JsonResponse({'redirect': reverse('plan')})
