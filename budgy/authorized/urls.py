from django.urls import path
from django.contrib import admin
from . import views

urlpatterns = [
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("register/", views.register, name="register"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("reset/<uidb64>/<token>/", views.reset_password, name="reset_password"),
]
