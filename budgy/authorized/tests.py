from django.test import TestCase

# authorized/tests.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from home.models import Account

from unittest.mock import patch
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes


class AuthorizedViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        # สร้าง user ตัวอย่าง
        self.user = User.objects.create_user(username="testuser", password="testpass")
        Account.objects.create(
            user=self.user, account_name="Cash", type_acc="cash", balance=0.0
        )

    # -------------------- LOGIN --------------------
    def test_login_page_loads(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "authorized/login.html")

    def test_login_success(self):
        response = self.client.post(
            reverse("login"),
            {"username": "testuser", "password": "testpass"},
            follow=True,
        )
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertRedirects(
            response, reverse("home", kwargs={"user_id": self.user.id})
        )

    def test_login_invalid_user(self):
        response = self.client.post(
            reverse("login"),
            {"username": "wronguser", "password": "wrongpass"},
            follow=True,
        )
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertContains(response, "This user is not registry yet")

    def test_login_already_authenticated(self):
        # Login ก่อนทดสอบ
        self.client.login(username="testuser", password="testpass")
        response = self.client.get(reverse("login"), follow=True)
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertRedirects(
            response, reverse("home", kwargs={"user_id": self.user.id})
        )

    # -------------------- LOGOUT --------------------
    def test_logout_redirects(self):
        # Login ก่อน logout
        self.client.login(username="testuser", password="testpass")
        response = self.client.get(reverse("logout"), follow=True)
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertRedirects(response, reverse("login"))

    # -------------------- REGISTER --------------------
    def test_register_page_loads(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "authorized/register.html")

    def test_register_success(self):
        response = self.client.post(
            reverse("register"),
            {
                "Username": "newuser",
                "Password": "newpass",
                "confirm_password": "newpass",
                "email": "newuser@test.com",
            },
            follow=True,
        )
        self.assertTrue(User.objects.filter(username="newuser").exists())
        new_user = User.objects.get(username="newuser")
        self.assertTrue(
            Account.objects.filter(user=new_user, account_name="Cash").exists()
        )
        self.assertTemplateUsed(response, "authorized/login.html")
        self.assertContains(response, "Register success")

    def test_register_password_mismatch(self):
        response = self.client.post(
            reverse("register"),
            {
                "Username": "user2",
                "Password": "pass1",
                "confirm_password": "pass2",
                "email": "user2@test.com",
            },
        )
        self.assertContains(response, "Password not match, Please try again.")
        self.assertFalse(User.objects.filter(username="user2").exists())

    def test_register_duplicate_username(self):
        response = self.client.post(
            reverse("register"),
            {
                "Username": "testuser",
                "Password": "testpass",
                "confirm_password": "testpass",
                "email": "duplicate@test.com",
            },
        )
        self.assertContains(
            response, "This Username already registry, Please try again."
        )

    def test_register_already_authenticated(self):
        # Login ก่อนทดสอบ
        self.client.login(username="testuser", password="testpass")
        response = self.client.get(reverse("register"), follow=True)
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertRedirects(
            response, reverse("home", kwargs={"user_id": self.user.id})
        )


# -------------------------Iteration3--------------------------------


class PasswordViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        # สร้าง user ตัวอย่าง
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="123456"
        )

    @patch("authorized.views.send_email")
    def test_forgot_password_success(self, mock_send_email):
        """
        กรณีใส่ email ถูกต้อง → ส่งลิงก์ reset และ redirect ไป login
        """
        response = self.client.post(
            reverse("forgot_password"),
            {"email": "test@example.com"},
        )

        # เช็ค redirect
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))

        # มีการส่ง email
        mock_send_email.assert_called_once()

    def test_forgot_password_email_not_found(self):
        """
        กรณี email ไม่ถูกต้อง → redirect กลับ forgot_password พร้อมแสดง error
        """
        response = self.client.post(
            reverse("forgot_password"),
            {"email": "notcorrect@example.com"},
            follow=True,
        )

        # หลัง follow จะเป็น status 200 (HTML)
        self.assertEqual(response.status_code, 200)

        # ตรวจ redirect chain
        self.assertEqual(response.redirect_chain, [(reverse("forgot_password"), 302)])

        # ตรวจว่ามีข้อความ error
        self.assertContains(response, "Email not found.")

    def test_reset_password_invalid_uid(self):

        response = self.client.get(
            reverse("reset_password", kwargs={"uidb64": "invalid", "token": "abc"}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "authorized/login.html")
        self.assertContains(response, "Invalid reset link.")

    def test_reset_password_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        bad_token = "invalidtoken123"

        response = self.client.get(
            reverse("reset_password", kwargs={"uidb64": uid, "token": bad_token}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "authorized/forgot_password.html")
        self.assertContains(response, "Reset link expired or invalid.")

    def test_reset_password_mismatch(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        response = self.client.post(
            reverse("reset_password", kwargs={"uidb64": uid, "token": token}),
            {"password": "123", "confirm": "456"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passwords do not match.")

    def test_reset_password_success(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        response = self.client.post(
            reverse("reset_password", kwargs={"uidb64": uid, "token": token}),
            {"password": "newpass123", "confirm": "newpass123"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password reset successfully.")

        # เช็คว่า login ผ่านจริง
        login_success = self.client.login(username="testuser", password="newpass123")
        self.assertTrue(login_success)
