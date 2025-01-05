from django.urls import path
from . import views

urlpatterns = [
    path('advisor/<int:advisor_id>/', views.advisor_detail, name='advisor_detail'),
]
