from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('advisor/<int:advisor_id>/', views.advisor_detail, name='advisor_detail'),
    path('login/send-otp/', views.request_login_otp, name='login-send-otp'),
    path('login/verify-otp/', views.verify_login_otp, name='login-verify-otp'),
    path('login/', views.login_view, name='login'),
    path('', views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

]

