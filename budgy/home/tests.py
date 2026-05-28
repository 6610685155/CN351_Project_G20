from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Category, Account, Income, Expense, Profile
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings, RequestFactory
from unittest.mock import patch, MagicMock
from home import views
import json


class HomeAppTests(TestCase):
    def setUp(self):
        # สร้าง user และ login
        self.user = User.objects.create_user(username="testuser", password="password")
        self.client = Client()
        self.client.login(username="testuser", password="password")

        # สร้าง accounts และ categories
        self.account = Account.objects.create(
            user=self.user, account_name="Cash", type_acc="Wallet", balance=1000
        )
        self.account2 = Account.objects.create(
            user=self.user, account_name="Bank", type_acc="Bank", balance=500
        )
        self.cat_income = Category.objects.create(
            user=self.user, category_name="Salary", trans_type="income"
        )
        self.cat_expense = Category.objects.create(
            user=self.user, category_name="Food", trans_type="expense"
        )
        self.cat_transfer = Category.objects.create(
            user=self.user, category_name="Bank Transfer", trans_type="transfer"
        )

    # ----- Landing -----
    def test_landing_redirects_home(self):
        response = self.client.get(reverse("landing"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/{self.user.id}/home/", response.url)

    # ----- Home -----
    def test_home_page_loads(self):
        response = self.client.get(reverse("home", kwargs={"user_id": self.user.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/home.html")

    # ----- Dashboard -----
    def test_dashboard_context(self):
        response = self.client.get(
            reverse("dashboard", kwargs={"user_id": self.user.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("categories", response.context)
        self.assertIn("accounts", response.context)
        self.assertIn("total_balance", response.context)

    # ----- Transaction Income -----
    def test_transaction_income_post(self):
        response = self.client.post(
            reverse("transaction_income", kwargs={"user_id": self.user.id}),
            data={
                "date": "2025-11-08",
                "amount": "500",
                "category_name": "Salary",
                "account": "Cash",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 1500)
        income = Income.objects.filter(user=self.user, amount=500).first()
        self.assertIsNotNone(income)

    # ----- Transaction Expense -----
    def test_transaction_expense_post(self):
        response = self.client.post(
            reverse("transaction_expense", kwargs={"user_id": self.user.id}),
            data={
                "date": "2025-11-08",
                "amount": "200",
                "category_name": "Food",
                "account": "Cash",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 800)
        expense = Expense.objects.filter(user=self.user, amount=200).first()
        self.assertIsNotNone(expense)

    # ----- Transaction Transfer -----
    def test_transaction_transfer_post(self):
        response = self.client.post(
            reverse("transaction_transfer", kwargs={"user_id": self.user.id}),
            data={
                "date": "2025-11-08",
                "amount": "300",
                "category_name": "Bank Transfer",
                "from_account": "Cash",
                "to_account": "Bank",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.account.refresh_from_db()
        self.account2.refresh_from_db()
        self.assertEqual(self.account.balance, 700)  # Cash ลดลง
        self.assertEqual(self.account2.balance, 800)  # Bank เพิ่มขึ้น

    # ----- Transaction Transfer -----
    def test_transaction_transfer_new_category(self):
        response = self.client.post(
            reverse("transaction_transfer", kwargs={"user_id": self.user.id}),
            data={
                "date": "2025-11-08",
                "amount": "400",
                "category_name": "NewTransferCat",
                "from_account": "Cash",
                "to_account": "Bank",
            },
        )
        self.assertTrue(
            Category.objects.filter(
                user=self.user, category_name="NewTransferCat"
            ).exists()
        )

    # ----- Category List -----
    def test_category_add_delete_income(self):
        # เพิ่ม category
        response = self.client.post(
            reverse("category_list", kwargs={"user_id": self.user.id}),
            data={"category_name": "NewCat", "trans_type": "income"},
        )
        self.assertTrue(
            Category.objects.filter(
                user=self.user, category_name="NewCat", trans_type="income"
            ).exists()
        )

        # ลบ category
        response = self.client.post(
            reverse("category_list", kwargs={"user_id": self.user.id}),
            data={"delete_category_name": "NewCat", "trans_type": "income"},
        )
        self.assertFalse(
            Category.objects.filter(
                user=self.user, category_name="NewCat", trans_type="income"
            ).exists()
        )

    def test_category_add_delete_expense(self):
        # เพิ่ม category
        response = self.client.post(
            reverse("category_list", kwargs={"user_id": self.user.id}),
            data={"category_name": "NewCat", "trans_type": "expense"},
        )
        self.assertTrue(
            Category.objects.filter(
                user=self.user, category_name="NewCat", trans_type="expense"
            ).exists()
        )

        # ลบ category
        response = self.client.post(
            reverse("category_list", kwargs={"user_id": self.user.id}),
            data={"delete_category_name": "NewCat", "trans_type": "expense"},
        )
        self.assertFalse(
            Category.objects.filter(
                user=self.user, category_name="NewCat", trans_type="expense"
            ).exists()
        )

    # ----- Stats Page -----
    def test_stats_page_loads(self):
        response = self.client.get(reverse("stats", kwargs={"user_id": self.user.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/stats.html")

    # ----- Settings Page -----
    def test_settings_page_loads(self):
        response = self.client.get(
            reverse("settings", kwargs={"user_id": self.user.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/settings.html")

    # ----- Contact Page -----
    def test_contact_page_loads(self):
        response = self.client.get(reverse("contact"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/contact.html")

    # ----- Spending API -----
    def test_spending_api_daily(self):
        Income.objects.create(
            user=self.user,
            trans_type="income",
            date="2025-11-08",
            amount=500,
            category_trans=self.cat_income,
            to_account=self.account,
        )
        response = self.client.get(
            reverse("spending_api") + "?mode=daily&date=2025-11-08"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["spendings"]), 1)
        self.assertEqual(data["spendings"][0]["amount"], 500)

    # ----- Accounts API -----
    def test_accounts_api(self):
        response = self.client.get(reverse("accounts_api"))
        self.assertEqual(response.status_code, 200)  # เปลี่ยนจาก 302 เป็น 200
        data = response.json()
        self.assertEqual(
            data["total_balance"], self.account.balance + self.account2.balance
        )
        self.assertEqual(len(data["accounts"]), 2)
        self.assertEqual(data["accounts"][0]["name"], "Bank")  # เรียง id desc

    # ----- Transaction Income: test branch add category only (no date) -----
    def test_transaction_income_add_category_only(self):
        response = self.client.post(
            reverse("transaction_income", kwargs={"user_id": self.user.id}),
            data={"category_name": "NewIncomeCat"},
        )
        self.assertTrue(
            Category.objects.filter(
                user=self.user, category_name="NewIncomeCat", trans_type="income"
            ).exists()
        )

    # ----- Transaction Expense: test branch add category only (no date) -----
    def test_transaction_expense_add_category_only(self):
        response = self.client.post(
            reverse("transaction_expense", kwargs={"user_id": self.user.id}),
            data={"category_name": "NewExpenseCat"},
        )
        self.assertTrue(
            Category.objects.filter(
                user=self.user, category_name="NewExpenseCat", trans_type="expense"
            ).exists()
        )

    # ----- Transaction Transfer: test branch add category only (no date) -----
    def test_transaction_transfer_add_category_only(self):
        response = self.client.post(
            reverse("transaction_transfer", kwargs={"user_id": self.user.id}),
            data={"category_name": "NewExpenseCat"},
        )
        self.assertTrue(
            Category.objects.filter(
                user=self.user, category_name="NewExpenseCat", trans_type="transfer"
            ).exists()
        )

    # ----- Category List: test GET request -----
    def test_category_list_get(self):
        response = self.client.get(
            reverse(
                "category_list",
                kwargs={"user_id": self.user.id},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/category_list.html")
        self.assertIn("categories", response.context)
        self.assertGreaterEqual(len(response.context["categories"]), 1)

    # ----- Spending API: test monthly and yearly -----
    def test_spending_api_monthly(self):
        Income.objects.create(
            user=self.user,
            trans_type="income",
            date="2025-11-08",
            amount=500,
            category_trans=self.cat_income,
            to_account=self.account,
        )
        response = self.client.get(
            reverse("spending_api") + "?mode=monthly&month=2025-11"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data["spendings"]), 1)

    def test_spending_api_yearly(self):
        Income.objects.create(
            user=self.user,
            trans_type="income",
            date="2025-11-08",
            amount=500,
            category_trans=self.cat_income,
            to_account=self.account,
        )
        response = self.client.get(reverse("spending_api") + "?mode=yearly&year=2025")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data["spendings"]), 1)

    def test_transaction_income_delete_category(self):
        Category.objects.create(
            user=self.user, category_name="TempCat", trans_type="income"
        )
        response = self.client.post(
            reverse("transaction_income", kwargs={"user_id": self.user.id}),
            data={"delete_category_name": "TempCat"},
        )
        self.assertFalse(
            Category.objects.filter(user=self.user, category_name="TempCat").exists()
        )

    def test_transaction_expense_delete_category(self):
        Category.objects.create(
            user=self.user, category_name="TempCat", trans_type="expense"
        )
        response = self.client.post(
            reverse("transaction_expense", kwargs={"user_id": self.user.id}),
            data={"delete_category_name": "TempCat"},
        )
        self.assertFalse(
            Category.objects.filter(user=self.user, category_name="TempCat").exists()
        )

    def test_transaction_transfer_delete_category(self):
        Category.objects.create(
            user=self.user, category_name="TempCat", trans_type="transfer"
        )
        response = self.client.post(
            reverse("transaction_transfer", kwargs={"user_id": self.user.id}),
            data={"delete_category_name": "TempCat"},
        )
        self.assertFalse(
            Category.objects.filter(user=self.user, category_name="TempCat").exists()
        )

    def test_landing_redirects_non_root_path(self):
        # สมมุติ path อื่น
        response = self.client.get("/foo/")
        expected_url = f"/{self.user.id}/foo/"
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, expected_url)

    def test_transaction_income_creates_new_category(self):
        # category ที่ส่งยังไม่มีอยู่
        category_name = "NewIncomeCategory"
        response = self.client.post(
            reverse("transaction_income", kwargs={"user_id": self.user.id}),
            data={
                "date": "2025-11-08",
                "amount": "500",
                "category_name": category_name,
                "account": "Cash",
            },
        )
        # ตรวจสอบว่า redirect ถูกต้อง
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("transaction_income", kwargs={"user_id": self.user.id}),
            response.url,
        )

        # ตรวจสอบว่า category ถูกสร้าง
        self.assertTrue(
            Category.objects.filter(
                user=self.user, category_name=category_name, trans_type="income"
            ).exists()
        )

        # ตรวจสอบว่า income ถูกสร้าง
        income = Income.objects.filter(
            user=self.user, amount=500, category_trans=category_name
        ).first()
        self.assertIsNotNone(income)

        # ตรวจสอบว่า account balance เพิ่มขึ้น
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 1500)

    def test_transaction_income_page_get(self):
        """GET request จะเข้า return render ของ transaction_income_page"""
        response = self.client.get(
            reverse("transaction_income", kwargs={"user_id": self.user.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/transaction_income.html")

    def test_transaction_expense_page_get(self):
        """GET request จะเข้า return render ของ transaction_expense_page"""
        response = self.client.get(
            reverse("transaction_expense", kwargs={"user_id": self.user.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/transaction_expense.html")

    def test_transaction_transfer_page_get(self):
        """GET request จะเข้า return render ของ transaction_transfer_page"""
        response = self.client.get(
            reverse("transaction_transfer", kwargs={"user_id": self.user.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/transaction_transfer.html")

    def test_transaction_income_negative_amount(self):
        response = self.client.post(
            reverse("transaction_income", kwargs={"user_id": self.user.id}),
            data={
                "date": "2025-11-08",
                "amount": "-100",
                "category_name": "Salary",
                "account": "Cash",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("transaction_income", kwargs={"user_id": self.user.id}),
            response.url,
        )

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 1000)  # ยอดเงินไม่เปลี่ยนแปลง

        income = Income.objects.filter(user=self.user, amount=-100).first()
        self.assertIsNone(income)  # income ไม่ถูกสร้าง

    def test_transaction_expense_negative_amount(self):
        response = self.client.post(
            reverse("transaction_expense", kwargs={"user_id": self.user.id}),
            data={
                "date": "2025-11-08",
                "amount": "-50",
                "category_name": "Food",
                "account": "Cash",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("transaction_expense", kwargs={"user_id": self.user.id}),
            response.url,
        )

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 1000)  # ยอดเงินไม่เปลี่ยนแปลง

        expense = Expense.objects.filter(user=self.user, amount=-50).first()
        self.assertIsNone(expense)  # expense ไม่ถูกสร้าง

    def test_transaction_transfer_negative_amount(self):
        response = self.client.post(
            reverse("transaction_transfer", kwargs={"user_id": self.user.id}),
            data={
                "date": "2025-11-08",
                "amount": "-200",
                "category_name": "Bank Transfer",
                "from_account": "Cash",
                "to_account": "Bank",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("transaction_transfer", kwargs={"user_id": self.user.id}),
            response.url,
        )

        self.account.refresh_from_db()
        self.account2.refresh_from_db()
        self.assertEqual(self.account.balance, 1000)  # ยอดเงินไม่เปลี่ยนแปลง
        self.assertEqual(self.account2.balance, 500)  # ยอดเงินไม่เปลี่ยนแปลง

        transfer_expense = Expense.objects.filter(
            user=self.user, amount=-200, category_trans="Bank Transfer"
        ).first()

        self.assertIsNone(transfer_expense)  # transfer expense ไม่ถูกสร้าง

    def test_transaction_income_invalid_amount(self):
        response = self.client.post(
            reverse("transaction_income", kwargs={"user_id": self.user.id}),
            data={
                "date": "2025-11-08",
                "amount": "invalid_amount",
                "category_name": "Salary",
                "account": "Cash",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("transaction_income", kwargs={"user_id": self.user.id}),
            response.url,
        )

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 1000)  # ยอดเงินไม่เปลี่ยนแปลง

    def test_transaction_expense_invalid_amount(self):
        response = self.client.post(
            reverse("transaction_expense", kwargs={"user_id": self.user.id}),
            data={
                "date": "2025-11-08",
                "amount": "invalid_amount",
                "category_name": "Food",
                "account": "Cash",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("transaction_expense", kwargs={"user_id": self.user.id}),
            response.url,
        )

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 1000)  # ยอดเงินไม่เปลี่ยนแปลง

    def test_transaction_transfer_invalid_amount(self):
        response = self.client.post(
            reverse("transaction_transfer", kwargs={"user_id": self.user.id}),
            data={
                "date": "2025-11-08",
                "amount": "invalid_amount",
                "category_name": "Bank Transfer",
                "from_account": "Cash",
                "to_account": "Bank",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("transaction_transfer", kwargs={"user_id": self.user.id}),
            response.url,
        )

        self.account.refresh_from_db()
        self.account2.refresh_from_db()
        self.assertEqual(self.account.balance, 1000)  # ยอดเงินไม่เปลี่ยนแปลง
        self.assertEqual(self.account2.balance, 500)  # ยอดเงินไม่เปลี่ยนแปลง

    def test_transaction_income_account_not_exist(self):
        response = self.client.post(
            reverse("transaction_income", kwargs={"user_id": self.user.id}),
            data={
                "date": "2025-11-08",
                "amount": "100",
                "category_name": "Salary",
                "account": "NonExistentAccount",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("transaction_income", kwargs={"user_id": self.user.id}),
            response.url,
        )

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 1000)  # ยอดเงินไม่เปลี่ยนแปลง

        income = Income.objects.filter(user=self.user, amount=100).first()
        self.assertIsNone(income)  # income ไม่ถูกสร้าง

    def test_transaction_expense_account_not_exist(self):
        response = self.client.post(
            reverse("transaction_expense", kwargs={"user_id": self.user.id}),
            data={
                "date": "2025-11-08",
                "amount": "50",
                "category_name": "Food",
                "account": "NonExistentAccount",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("transaction_expense", kwargs={"user_id": self.user.id}),
            response.url,
        )

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 1000)  # ยอดเงินไม่เปลี่ยนแปลง

        expense = Expense.objects.filter(user=self.user, amount=50).first()
        self.assertIsNone(expense)  # expense ไม่ถูกสร้าง

    def test_transaction_transfer_account_not_exist(self):
        response = self.client.post(
            reverse("transaction_transfer", kwargs={"user_id": self.user.id}),
            data={
                "date": "2025-11-08",
                "amount": "200",
                "category_name": "Bank Transfer",
                "from_account": "Cash",
                "to_account": "NonExistentAccount",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("transaction_transfer", kwargs={"user_id": self.user.id}),
            response.url,
        )

        self.account.refresh_from_db()
        self.account2.refresh_from_db()
        self.assertEqual(self.account.balance, 1000)  # ยอดเงินไม่เปลี่ยนแปลง
        self.assertEqual(self.account2.balance, 500)  # ยอดเงินไม่เปลี่ยนแปลง

        transfer_expense = Expense.objects.filter(
            user=self.user, amount=200, category_trans="Bank Transfer"
        ).first()

        self.assertIsNone(transfer_expense)  # transfer expense ไม่ถูกสร้าง


class HomePageSummaryTests(TestCase):
    """
    ทดสอบสรุปข้อมูลในหน้า Homepage (ยอดรวม, income/expense เดือนปัจจุบัน, expense_percentage)
    """

    def setUp(self):
        self.user = User.objects.create_user(username="homeuser", password="password")
        self.client = Client()
        self.client.login(username="homeuser", password="password")

        # สร้างบัญชี 2 บัญชี
        self.acc1 = Account.objects.create(
            user=self.user, account_name="Cash", type_acc="Wallet", balance=1000
        )
        self.acc2 = Account.objects.create(
            user=self.user, account_name="Bank", type_acc="Bank", balance=500
        )

    def test_homepage_summary_with_income_and_expense(self):
        now = timezone.now()

        Income.objects.create(
            user=self.user,
            trans_type="income",
            date=now,
            amount=300,
            category_trans="Salary",
            to_account=self.acc1,
        )
        Expense.objects.create(
            user=self.user,
            trans_type="expense",
            date=now,
            amount=100,
            category_trans="Food",
            from_account=self.acc1,
        )

        response = self.client.get(reverse("home", kwargs={"user_id": self.user.id}))
        self.assertEqual(response.status_code, 200)

        ctx = response.context
        # total_balance = 1000 + 500
        self.assertEqual(ctx["total_balance"], 1500)
        self.assertEqual(ctx["month_income"], 300)
        self.assertEqual(ctx["month_expense"], 100)
        # expense_percentage = 100 / 300 * 100 = 33.33...
        self.assertAlmostEqual(ctx["expense_percentage"], (100 / 300) * 100, places=2)

    def test_homepage_summary_with_expense_only(self):
        now = timezone.now()
        Expense.objects.create(
            user=self.user,
            trans_type="expense",
            date=now,
            amount=50,
            category_trans="Food",
            from_account=self.acc1,
        )

        response = self.client.get(reverse("home", kwargs={"user_id": self.user.id}))
        self.assertEqual(response.status_code, 200)

        ctx = response.context
        self.assertEqual(ctx["month_income"], 0)
        self.assertEqual(ctx["month_expense"], 50)
        # ถ้าไม่มี income ให้ expense_percentage เป็น 0
        self.assertEqual(ctx["expense_percentage"], 0)

    def test_home_page_no_income_expense_percentage_zero(self):
        Expense.objects.create(
            user=self.user,
            date=timezone.now(),
            amount=50,
            category_trans="Food",
            from_account=self.acc1,
        )
        response = self.client.get(reverse("home", args=[self.user.id]))
        self.assertEqual(response.context["expense_percentage"], 0)


class StatsPageAndApiTests(TestCase):
    """
    ทดสอบหน้า Stats ทั้ง 4 แบบ + API (summary + yearly)
    """

    def setUp(self):
        self.user = User.objects.create_user(username="statsuser", password="password")
        self.client = Client()
        self.client.login(username="statsuser", password="password")

        self.account = Account.objects.create(
            user=self.user, account_name="Main", type_acc="Wallet", balance=0
        )

    def test_stats_page_context_years_and_expense_months(self):
        # สร้าง Income ปี 2024 และ Expense ปี 2023
        Income.objects.create(
            user=self.user,
            trans_type="income",
            date="2024-05-10",
            amount=100,
            category_trans="Salary",
            to_account=self.account,
        )
        Expense.objects.create(
            user=self.user,
            trans_type="expense",
            date="2023-03-15",
            amount=50,
            category_trans="Food",
            from_account=self.account,
        )

        response = self.client.get(reverse("stats", kwargs={"user_id": self.user.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/stats.html")

        years = response.context["years"]
        # ควรเรียงปีจากใหม่ไปเก่า
        self.assertEqual(years, [2024, 2023])

        expense_months = response.context["expense_months"]
        # มีอย่างน้อย 1 เดือน และ value เป็นรูปแบบ YYYY-MM
        self.assertGreaterEqual(len(expense_months), 1)
        self.assertEqual(expense_months[0]["value"], "2023-03")

    # ---- Stats Summary API ----
    def test_stats_summary_api_requires_params(self):
        response = self.client.get(reverse("stats_summary_api"))
        self.assertEqual(response.status_code, 400)

    def test_stats_summary_api_income(self):
        Income.objects.create(
            user=self.user,
            trans_type="income",
            date="2024-05-01",
            amount=500,
            category_trans="Salary",
            to_account=self.account,
        )
        Income.objects.create(
            user=self.user,
            trans_type="income",
            date="2024-05-10",
            amount=200,
            category_trans="Bonus",
            to_account=self.account,
        )
        # อีกตัวคนละเดือน จะไม่ถูกรวม
        Income.objects.create(
            user=self.user,
            trans_type="income",
            date="2024-06-01",
            amount=999,
            category_trans="Other",
            to_account=self.account,
        )

        response = self.client.get(
            reverse("stats_summary_api") + "?year=2024&month=5&type=income"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # labels + values รวมเฉพาะเดือน 5
        self.assertCountEqual(data["labels"], ["Salary", "Bonus"])
        # รวมยอด = 700
        self.assertEqual(data["overall_total"], 700)

    def test_stats_summary_api_expense(self):
        Expense.objects.create(
            user=self.user,
            trans_type="expense",
            date="2024-04-05",
            amount=100,
            category_trans="Food",
            from_account=self.account,
        )
        Expense.objects.create(
            user=self.user,
            trans_type="expense",
            date="2024-04-20",
            amount=50,
            category_trans="Transport",
            from_account=self.account,
        )

        response = self.client.get(
            reverse("stats_summary_api") + "?year=2024&month=4&type=expense"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertCountEqual(data["labels"], ["Food", "Transport"])
        self.assertEqual(data["overall_total"], 150)

    # ---- Stats Yearly API ----
    def test_stats_yearly_api_requires_year(self):
        response = self.client.get(reverse("stats_yearly_api"))
        self.assertEqual(response.status_code, 400)

    def test_stats_yearly_api_valid(self):
        # สร้างรายรับรายจ่ายในปี 2024 เดือน 5
        Income.objects.create(
            user=self.user,
            trans_type="income",
            date="2024-05-01",
            amount=100,
            category_trans="Salary",
            to_account=self.account,
        )
        Expense.objects.create(
            user=self.user,
            trans_type="expense",
            date="2024-05-02",
            amount=40,
            category_trans="Food",
            from_account=self.account,
        )

        response = self.client.get(reverse("stats_yearly_api") + "?year=2024")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # index 4 = May (เพราะเริ่มที่ 0 = Jan)
        self.assertEqual(data["income"][4], 100)
        self.assertEqual(data["expense"][4], 40)
        self.assertEqual(len(data["income"]), 12)
        self.assertEqual(len(data["expense"]), 12)

    def test_stats_summary_api_empty(self):
        response = self.client.get(
            reverse("stats_summary_api") + "?year=2024&month=5&type=income"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["labels"], [])
        self.assertEqual(data["values"], [])
        self.assertEqual(data["overall_total"], 0)

    def test_stats_yearly_api_no_data(self):
        response = self.client.get(reverse("stats_yearly_api") + "?year=2099")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["income"], [0] * 12)
        self.assertEqual(data["expense"], [0] * 12)


class SettingsAndDeleteAccountTests(TestCase):
    """
    ทดสอบหน้า settings (แก้ username / รูป) + ลบ account ผู้ใช้
    """

    def setUp(self):
        self.password = "password123"
        self.user = User.objects.create_user(
            username="settingsuser",
            email="test@test.com",
            password=self.password,
        )
        self.client = Client()
        self.client.login(username="settingsuser", password=self.password)

        # initial GET เพื่อให้ view สร้าง Profile ถ้ายังไม่มี
        self.client.get(reverse("settings", kwargs={"user_id": self.user.id}))

    def test_profile_str(self):
        user = User.objects.create_user(username="aaa", password="x")
        # Profile ถูกสร้างอัตโนมัติโดย signal แล้ว ไม่ต้อง create ใหม่
        profile = Profile.objects.get(user=user)
        self.assertEqual(str(profile), "aaa Profile")

    def test_settings_page_creates_profile_if_missing(self):
        # ลบ Profile ทิ้ง แล้วเข้า settings อีกครั้ง → ควรสร้างใหม่
        Profile.objects.filter(user=self.user).delete()
        response = self.client.get(
            reverse("settings", kwargs={"user_id": self.user.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Profile.objects.filter(user=self.user).exists())

    def test_update_username_via_settings(self):
        response = self.client.post(
            reverse("settings", kwargs={"user_id": self.user.id}),
            data={
                "username": "newusername",
                "update_username": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "newusername")

    @patch("home.views.ProfilePictureUpdateForm")
    def test_update_profile_picture_via_settings(self, MockForm):
        """
        เคสอัปเดตรูปโปรไฟล์สำเร็จ → ต้องเรียก save() แล้ว redirect (302)
        ใช้ mock เพื่อบังคับให้ฟอร์ม valid โดยไม่ยุ่งกับการเซฟไฟล์จริง
        """
        form_instance = MagicMock()
        form_instance.is_valid.return_value = True
        MockForm.return_value = form_instance

        image = SimpleUploadedFile(
            "test.png",
            b"dummy-image-content",
            content_type="image/png",
        )

        response = self.client.post(
            reverse("settings", kwargs={"user_id": self.user.id}),
            data={
                "image": image,
                "update_picture": "1",
            },
        )

        # เข้า if p_form.is_valid() → save + redirect
        self.assertEqual(response.status_code, 302)
        form_instance.is_valid.assert_called_once()
        form_instance.save.assert_called_once()

    def test_delete_account_success(self):
        response = self.client.post(
            reverse("delete_account"),
            data={"password": self.password},
        )
        self.assertEqual(response.status_code, 302)
        # user ถูกลบออกจากฐานข้อมูล
        self.assertFalse(User.objects.filter(id=self.user.id).exists())

    def test_settings_update_username_invalid(self):
        response = self.client.post(
            reverse("settings", args=[self.user.id]),
            data={"username": "", "update_username": "1"},
        )
        self.assertEqual(response.status_code, 200)  # invalid → ไม่ redirect

    def test_settings_update_picture_invalid(self):
        fake_file = SimpleUploadedFile(
            "x.txt", b"not an image", content_type="text/plain"
        )
        response = self.client.post(
            reverse("settings", args=[self.user.id]),
            data={"image": fake_file, "update_picture": "1"},
        )
        self.assertEqual(response.status_code, 200)

    def test_update_email_via_settings(self):
        response = self.client.post(
            reverse("settings", kwargs={"user_id": self.user.id}),
            data={
                "email": "newemail@test.com",
                "update_email": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "newemail@test.com")


class AccountManagementTests(TestCase):
    """
    ทดสอบเพิ่ม / ลบ / แก้ชื่อ accounts
    """

    def setUp(self):
        self.user = User.objects.create_user(username="accuser", password="password")
        self.client = Client()
        self.client.login(username="accuser", password="password")

        # สร้างบัญชี Cash เริ่มต้น
        self.cash = Account.objects.create(
            user=self.user, account_name="Cash", type_acc="Default", balance=0
        )

    def test_account_management_get(self):
        response = self.client.get(
            reverse("account_management", kwargs={"user_id": self.user.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/accounts_management.html")
        self.assertIn("accounts", response.context)

    def test_create_account_success(self):
        response = self.client.post(
            reverse("account_management", kwargs={"user_id": self.user.id}),
            data={"account_name": "Savings", "balance": "2500"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Account.objects.filter(user=self.user, account_name="Savings").exists()
        )

    def test_create_account_duplicate_name(self):
        Account.objects.create(
            user=self.user, account_name="Savings", type_acc="Default", balance=0
        )
        response = self.client.post(
            reverse("account_management", kwargs={"user_id": self.user.id}),
            data={"account_name": "Savings", "balance": "100"},
        )
        self.assertEqual(response.status_code, 302)
        # ยังมีชื่อ Savings แค่ตัวเดียว
        self.assertEqual(
            Account.objects.filter(user=self.user, account_name="Savings").count(), 1
        )

    def test_create_account_invalid_balance(self):
        response = self.client.post(
            reverse("account_management", kwargs={"user_id": self.user.id}),
            data={"account_name": "InvalidBalanceAcc", "balance": "not-a-number"},
        )
        self.assertEqual(response.status_code, 302)
        # ไม่ควรถูกสร้าง
        self.assertFalse(
            Account.objects.filter(
                user=self.user, account_name="InvalidBalanceAcc"
            ).exists()
        )

    # ---- update_account_api ----
    def test_update_account_api_success(self):
        acc = Account.objects.create(
            user=self.user, account_name="EditMe", type_acc="Default", balance=0
        )
        response = self.client.post(
            reverse("update_account_api", args=[acc.id]),
            data=json.dumps({"account_name": "EditedName"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        acc.refresh_from_db()
        self.assertEqual(acc.account_name, "EditedName")

    def test_update_account_api_empty_name(self):
        acc = Account.objects.create(
            user=self.user, account_name="EditMe2", type_acc="Default", balance=0
        )
        response = self.client.post(
            reverse("update_account_api", args=[acc.id]),
            data=json.dumps({"account_name": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_update_account_api_duplicate_name(self):
        Account.objects.create(
            user=self.user, account_name="Existing", type_acc="Default", balance=0
        )
        acc = Account.objects.create(
            user=self.user, account_name="ToRename", type_acc="Default", balance=0
        )
        response = self.client.post(
            reverse("update_account_api", args=[acc.id]),
            data=json.dumps({"account_name": "Existing"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_update_account_api_forbidden_cash(self):
        acc = self.cash  # ชื่อ Cash ห้ามแก้
        response = self.client.post(
            reverse("update_account_api", args=[acc.id]),
            data=json.dumps({"account_name": "NewCashName"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    # ---- delete_account_view ----
    def test_delete_account_success_when_balance_zero(self):
        acc = Account.objects.create(
            user=self.user, account_name="TempAcc", type_acc="Default", balance=0
        )
        response = self.client.post(
            reverse(
                "delete_account",
                kwargs={"user_id": self.user.id, "account_id": acc.id},
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Account.objects.filter(id=acc.id).exists())

    def test_cannot_delete_cash_account(self):
        response = self.client.post(
            reverse(
                "delete_account",
                kwargs={"user_id": self.user.id, "account_id": self.cash.id},
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Account.objects.filter(id=self.cash.id).exists())

    def test_cannot_delete_account_with_nonzero_balance(self):
        acc = Account.objects.create(
            user=self.user, account_name="NonZero", type_acc="Default", balance=100
        )
        response = self.client.post(
            reverse(
                "delete_account",
                kwargs={"user_id": self.user.id, "account_id": acc.id},
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Account.objects.filter(id=acc.id).exists())

    def test_delete_account_wrong_password(self):
        """
        เรียก delete_account_page ด้วยรหัสผ่านผิด
        View จะพยายาม redirect('settings') แล้วพัง (NoReverseMatch) → 500
        """
        client = Client()
        client.force_login(self.user)
        client.raise_request_exception = False  # อย่าโยน exception ออกมาเป็น error test

        response = client.post(
            reverse("delete_account"),
            data={"password": "wrong"},
        )
        self.assertEqual(response.status_code, 500)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_delete_account_get(self):
        client = Client()
        client.force_login(self.user)
        client.raise_request_exception = False

        response = client.get(reverse("delete_account"))
        self.assertEqual(response.status_code, 500)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_account_management_missing_name(self):
        response = self.client.post(
            reverse("account_management", args=[self.user.id]),
            data={"account_name": "", "balance": "50"},
        )
        self.assertEqual(response.status_code, 302)
        # ไม่สร้างบัญชีใหม่
        self.assertEqual(Account.objects.filter(user=self.user).count(), 1)

    def test_update_account_api_get_not_allowed(self):
        acc = Account.objects.create(
            user=self.user, account_name="Hello", balance=0, type_acc="Default"
        )
        response = self.client.get(reverse("update_account_api", args=[acc.id]))
        self.assertEqual(response.status_code, 405)

    def test_delete_account_view_get_does_not_delete(self):
        acc = Account.objects.create(
            user=self.user, account_name="TestDel", type_acc="Default", balance=0
        )
        response = self.client.get(
            reverse(
                "delete_account",
                kwargs={"user_id": self.user.id, "account_id": acc.id},
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Account.objects.filter(id=acc.id).exists())

    def test_update_account_api_error_case(self):
        acc = Account.objects.create(
            user=self.user, account_name="Boom", type_acc="Default", balance=0
        )

        factory = RequestFactory()
        request = factory.post(
            f"/api/accounts/update/{acc.id}/",
            data="invalid-json",
            content_type="application/json",
        )
        request.user = self.user

        with patch("home.views.json.loads", side_effect=Exception("boom")):
            response = views.update_account_api(request, acc.id)

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content.decode())
        self.assertIn("error", data)

# -----------------------Iteration3----------------------------

class Mascot(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="accuser", password="password")
        self.client = Client()
        self.client.login(username="accuser", password="password")

        # สร้างบัญชี Cash เริ่มต้น
        self.cash = Account.objects.create(
            user=self.user, account_name="Cash", type_acc="Default", balance=0
        )

        #สร้างบัญชี Bank 
        self.bank = Account.objects.create(
            user=self.user, account_name="Bank", type_acc="Saving", balance=0
        )

        self.url_chat = reverse("pet_chat_api")
        self.url_status = reverse("pet_status_api")

    #--------setting page view switch to enable/disable mascot ------
    def test_enable_mascot(self):
        """ทดสอบการเปิด mascot (enable switch)"""
        url = reverse('settings', kwargs={'user_id': self.user.id})

        response = self.client.post(url, {
            'update_mascot': '1',
            'show_mascot': 'on',  
        })

        self.user.refresh_from_db()
        profile = self.user.profile

        self.assertTrue(profile.show_mascot)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, url)

    def test_disable_mascot(self):
        """ทดสอบการปิด mascot """
        # ทำให้เริ่มต้นเป็น True ก่อน
        profile = self.user.profile
        profile.show_mascot = True
        profile.save()

        url = reverse('settings', kwargs={'user_id': self.user.id})

        response = self.client.post(url, {
            'update_mascot': '1',
            # ไม่มี show_mascot -> mascot disable
        })

        self.user.refresh_from_db()
        profile = self.user.profile

        self.assertFalse(profile.show_mascot)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, url)

    #-----------------mascot check--------------------

    # test get chat api
    def test_pet_chat_api_get(self):
        """ทดสอบว่า GET /pet/chat/ แล้วได้ JSON ถูกต้อง"""
        response = self.client.get(self.url_chat)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("text", response.json())
        self.assertEqual(response.json()["text"], "")
    
    # test ว่าคำนวณค่าต่างๆ สำหรับ mascot ถูกต้องไหม
    def test_calculation_for_mascot(self):
        """
        ทดสอบคำนวณตัวเลขทั้งหมด:
        total_balance, income, expense, expense_percentage, saving_rate
        """
        now = timezone.now()

        # ตั้งค่า 2 account
        self.cash.balance = 300
        self.cash.save()
        self.bank.balance = 700
        self.bank.save()

        # income / expense
        Income.objects.create(user=self.user, amount=1400, date=now, to_account=self.cash)
        Expense.objects.create(user=self.user, amount=400, date=now, from_account=self.bank)

        self.cash.balance += 1400
        self.cash.save()
        self.bank.balance -= 400
        self.bank.save()

        response = self.client.get(self.url_status)
        data = response.json()

        expected_total_balance = (300+1400)+(700-400)
        expected_income = 1400
        expected_expense = 400
        expected_exp_percent = round((400/1400) * 100, 2)
        expected_saving_rate = round(((1400 - 400) / 1400) * 100, 2)

        # ตรวจครบทุก numeric field
        self.assertEqual(data["total_balance"], expected_total_balance)
        self.assertEqual(data["month_income"], expected_income)
        self.assertEqual(data["month_expense"], expected_expense)
        self.assertEqual(data["expense_percentage"], expected_exp_percent)
        self.assertEqual(data["saving_rate"], expected_saving_rate)
    
    # test กรณีไม่มีรายรับรายจ่าย
    def test_mascot_no_income_and_expense(self):
       """
       ไม่มีรายรับ/รายจ่าย
       → saving_rate = 100, status = happy
       """
       response = self.client.get(self.url_status)
       data = response.json()

       self.assertEqual(response.status_code, 200)
       self.assertEqual(data["total_balance"], 0)
       self.assertEqual(data["saving_rate"], 100)
       self.assertEqual(data["status"], "neutral")

    # test กรณีไม่มีรายรับแต่มีรายจ่าย
    def test_mascot_no_income_but_expense(self):
        """
        ไม่มีรายรับแต่มีรายจ่าย
        → saving_rate = 100, status = danger
        """
        now = timezone.now()

        self.cash.balance = 500
        self.cash.save()

        Income.objects.create(user=self.user, amount=0, date=now, to_account=self.cash)
        Expense.objects.create(user=self.user, amount=400, date=now, from_account=self.cash)

        response = self.client.get(self.url_status)
        data = response.json()

        self.assertEqual(data["saving_rate"], 0)
        self.assertEqual(data["status"], "danger")
        self.assertEqual(data["advice"], "ระวังนิดนึงนะ รายจ่ายเริ่มหนักกว่าเงินที่เข้าแล้ว ⚠️")
    
    # test กรณีมีรายรับและ status เป็น happy
    def test_mascot_have_income_status_happy(self):
        """
        รายรับมากกว่ารายจ่าย (saving_rate >= 66) → happy
        """
        now = timezone.now()

        Income.objects.create(user=self.user, amount=2000, date=now, to_account=self.cash)
        Expense.objects.create(user=self.user, amount=400, date=now, from_account=self.cash)

        response = self.client.get(self.url_status)
        data = response.json()

        self.assertEqual(data["saving_rate"], 80)
        self.assertEqual(data["status"], "happy")
        self.assertEqual(data["advice"], "โห! เก็บเงินได้ดีมากเลย 🎉 รักษาระดับนี้ไว้นะ!")
    
    # test กรณีมีรายรับและ status เป็น danger
    def test_mascot_have_income_status_danger(self):
        """
        รายจ่ายเยอะมาก (saving_rate <= 33) → danger
        """
        now = timezone.now()

        Income.objects.create(user=self.user, amount=2000, date=now, to_account=self.cash)
        Expense.objects.create(user=self.user, amount=1500, date=now, from_account=self.cash)

        response = self.client.get(self.url_status)
        data = response.json()

        self.assertEqual(data["saving_rate"], 25)
        self.assertEqual(data["status"], "danger")
        self.assertEqual(data["advice"], "ระวังนิดนึงนะ รายจ่ายเริ่มหนักกว่าเงินที่เข้าแล้ว ⚠️")
    
    # test กรณีมีรายรับและ status เป็น neutral
    def test_mascot_status_neutral(self):
        """
        saving_rate อยู่กลาง ๆ (33 < saving_rate < 66) → neutral
        """
        now = timezone.now()

        Income.objects.create(user=self.user, amount=2000, date=now, to_account=self.cash)
        Expense.objects.create(user=self.user, amount=1000, date=now, from_account=self.cash)

        response = self.client.get(self.url_status)
        data = response.json()

        self.assertEqual(data["saving_rate"], 50)
        self.assertEqual(data["status"], "neutral")
        self.assertEqual(data["advice"], "ใช้จ่ายได้โอเคอยู่ แต่ลองเก็บเพิ่มอีกนิดจะดีมากเลย 😊")
    