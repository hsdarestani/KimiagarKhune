from .models import Advisor
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login

def advisor_detail(request, advisor_id):
    try:
        advisor = Advisor.objects.get(id=advisor_id)
        students = advisor.student_set.all() 
    except Advisor.DoesNotExist:
        advisor = None
        students = []

    return render(request, 'accounts/advisor_detail.html', {'advisor': advisor, 'students': students})


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
            context = {"error": "نام کاربری یا رمز عبور نادرست است."}
            return render(request, "accounts/login.html", context)
    return render(request, "accounts/login.html")
