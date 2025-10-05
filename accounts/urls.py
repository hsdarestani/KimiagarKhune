from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('advisor/<int:advisor_id>/', views.advisor_detail, name='advisor_detail'),
    path('login/', views.login_view, name='login'),
    path('', views.login_view, name='login'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

]

