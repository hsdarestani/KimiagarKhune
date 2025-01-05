from django.shortcuts import render
from .models import Advisor


def advisor_detail(request, advisor_id):
    try:
        advisor = Advisor.objects.get(id=advisor_id)
        students = advisor.student_set.all() 
    except Advisor.DoesNotExist:
        advisor = None
        students = []

    return render(request, 'accounts/advisor_detail.html', {'advisor': advisor, 'students': students})
