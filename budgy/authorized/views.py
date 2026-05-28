from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import authenticate
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import login as auth_login
from django.contrib.auth.models import User
from django.contrib import messages
from home.models import Account

from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes

# from django.core.mail import send_mail
from .utils.email import send_email
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password

# Create your views here.


# Login function
def login(request):
    if request.user.is_authenticated:
        # User is logged in, redirect to previous page or home
        return redirect(
            request.META.get("HTTP_REFERER") or "home", user_id=request.user.id
        )

    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(username=username, password=password)

        if user is not None:
            auth_login(request, user)
            # admin:index เป็น url ที่ Django กำหนดไว้ให้เป็นหน้า admin page
            # return redirect(reverse("admin:index"))

            return redirect(
                "home", user_id=request.user.id
            )  # return render(request, "room/home.html")

        else:
            messages.error(request, "This user is not registry yet")
            return redirect("login")

    return render(request, "authorized/login.html")


# Logout function
def logout(request):
    auth_logout(request)
    context = {"message": "You're Logout"}
    return redirect(reverse("login"), context)


# Register function
def register(request):
    if request.user.is_authenticated:
        # User is logged in, redirect to previous page or home
        return redirect(
            request.META.get("HTTP_REFERER") or "home", user_id=request.user.id
        )

    if request.method == "POST":
        username = request.POST["Username"]
        password = request.POST["Password"]
        email = request.POST["email"]
        password_again = request.POST["confirm_password"]

        if password != password_again:
            messages.error(request, "Password not match, Please try again.")
            return render(
                request,
                "authorized/register.html",
                {"message": "Password not match, Please try again."},
            )

        if User.objects.filter(username=username).exists():
            messages.error(request, "This Username already registry, Please try again.")
            return render(
                request,
                "authorized/register.html",
                {"message": "This Username already registry, Please try again."},
            )

        user = User.objects.create_user(
            username=username, password=password, email=email
        )

        Account.objects.create(
            user=user, account_name="Cash", type_acc="cash", balance=0.0
        )

        messages.success(request, "Register success")
        return render(
            request,
            "authorized/login.html",
            {"registry": "Register success"},
        )
    return render(request, "authorized/register.html")


# Forgot Password
def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "Email not found.")
            return redirect("forgot_password")

        # Generate token + uid
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        reset_link = request.build_absolute_uri(
            reverse("reset_password", kwargs={"uidb64": uid, "token": token})
        )

        # Send email
        send_email(
            to_email=email,
            subject="Reset Your Password",
            text_content=f"Click the link to reset your password:\n{reset_link}",
        )

        messages.success(request, "Password reset link sent to your email.")
        return redirect("login")

    return render(request, "authorized/forgot_password.html")


# Reset Password
def reset_password(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except Exception:
        messages.error(request, "Invalid reset link.")
        return redirect("login")

    if not default_token_generator.check_token(user, token):
        messages.error(request, "Reset link expired or invalid.")
        return redirect("forgot_password")

    if request.method == "POST":
        password = request.POST.get("password")
        confirm = request.POST.get("confirm")

        if password != confirm:
            messages.error(request, "Passwords do not match.")
            return redirect(
                reverse("reset_password", kwargs={"uidb64": uidb64, "token": token})
            )

        # Save new password
        user.password = make_password(password)
        user.save()

        messages.success(request, "Password reset successfully.")
        return redirect("login")

    return render(request, "authorized/reset_password.html")
