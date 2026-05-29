# import requests
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.utils.dateparse import parse_date
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Sum
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .models import Transaction, Account, Category, MonthReport, Income, Expense
import calendar
import json
from django.views.decorators.http import require_POST
from .forms import (
    UsernameUpdateForm,
    EmailUpdateForm,
    ProfilePictureUpdateForm,
    AccountDeleteForm,
)
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from .models import Profile
from django.db import connection


# Create your views here
@login_required(login_url="/login/")
def landing_page(request, user_id=None):
    if request.path == "/":
        return redirect("/" + str(request.user.id) + "/home/")
    return redirect("/" + str(request.user.id) + request.path)


@login_required(login_url="/login/")
def home_page(request, user_id):
    user = request.user

    # --- 1. คำนวณยอดเงินคงเหลือทั้งหมด ---
    # ดึงข้อมูล accounts ทั้งหมดของผู้ใช้ แล้วรวมยอด balance
    # หากไม่มี account เลย ให้ค่าเป็น 0
    total_balance = (
        Account.objects.filter(user=user).aggregate(Sum("balance"))["balance__sum"] or 0
    )

    # --- 2. คำนวณยอดรวมของเดือนปัจจุบัน ---
    current_year = datetime.now().year
    current_month = datetime.now().month

    # ยอดรวมรายรับของเดือนปัจจุบัน
    month_income = (
        Income.objects.filter(
            user=user, date__year=current_year, date__month=current_month
        ).aggregate(Sum("amount"))["amount__sum"]
        or 0
    )

    # ยอดรวมรายจ่ายของเดือนปัจจุบัน
    month_expense = (
        Expense.objects.filter(
            user=user, date__year=current_year, date__month=current_month
        ).aggregate(Sum("amount"))["amount__sum"]
        or 0
    )

    # --- 3. คำนวณสัดส่วนรายจ่ายต่อรายรับ ---
    # ป้องกันการหารด้วยศูนย์ หากเดือนนี้ยังไม่มีรายรับ
    if month_income > 0:
        expense_percentage = (month_expense / month_income) * 100
    else:
        expense_percentage = 0  # ถ้าไม่มีรายรับ ให้สัดส่วนเป็น 0

    # --- 4. สร้าง context เพื่อส่งข้อมูลไปที่ Template ---
    context = {
        "total_balance": total_balance,
        "month_income": month_income,
        "month_expense": month_expense,
        "expense_percentage": expense_percentage,
    }

    return render(request, "home/home.html", context)


@login_required(login_url="/login/")
def dashboard_today_page(request, user_id):
    user = request.user
    categories = Category.objects.filter(user=user)
    accounts = Account.objects.filter(user=user).order_by("-id")  # ตัวอย่างเรียงล่าสุด
    total_balance = sum(a.balance for a in accounts)

    context = {
        "categories": categories,
        "accounts": accounts,
        "total_balance": total_balance,
    }

    # ส่ง context เข้า render
    return render(request, "home/dashboard.html", context)


@login_required
def spending_api(request):
    mode = request.GET.get("mode")
    user = request.user
    spendings = Transaction.objects.filter(user=user)

    if mode == "daily":
        date_str = request.GET.get("date")
        if date_str:
            selected_date = parse_date(date_str)
            spendings = spendings.filter(date__date=selected_date)
    elif mode == "monthly":
        month_str = request.GET.get("month")  # YYYY-MM
        if month_str:
            year, month = map(int, month_str.split("-"))
            spendings = spendings.filter(date__year=year, date__month=month)
    elif mode == "yearly":
        year_str = request.GET.get("year")
        if year_str:
            spendings = spendings.filter(date__year=int(year_str))

    # แปลงเป็น list JSON
    data = [
        {
            "category": t.category_trans,
            "amount": t.amount,
            "type": t.trans_type,
        }
        for t in spendings.order_by("-date")  # เรียงจากล่าสุด
    ]

    return JsonResponse({"spendings": data})


@login_required
def accounts_api(request):
    user = request.user
    accounts = Account.objects.filter(user=user).order_by("-id")[:3]

    data = [
        {
            "name": acc.account_name,
            "balance": acc.balance,
        }
        for acc in accounts
    ]

    total_balance = sum(acc.balance for acc in Account.objects.filter(user=user))

    return JsonResponse({"accounts": data, "total_balance": total_balance})


@login_required(login_url="/login/")
@csrf_exempt
def category_list(request, user_id):
    user = request.user

    if request.method == "POST":
        # Add Category
        category_name = request.POST.get("category_name")
        trans_type = request.POST.get("trans_type")

        if category_name:
            # Avoid duplicate categories
            Category.objects.get_or_create(
                user=user, category_name=category_name, trans_type=trans_type
            )

        # Delete Category
        delete_name = request.POST.get("delete_category_name")

        if delete_name:
            Category.objects.filter(
                user=user, category_name=delete_name, trans_type=trans_type
            ).delete()

        return redirect(
            request.META.get("HTTP_REFERER") or "category_list", user_id=request.user.id
        )  # Redirect to the same page to refresh the list

    else:
        # GET Request: Fetch all categories for the user
        categories = Category.objects.filter(user=user)
        return render(
            request,
            "home/category_list.html",
            {"categories": categories},
        )


@login_required(login_url="/login/")
@csrf_exempt
def transaction_income_page(request, user_id):
    user_now = request.user
    transaction_type = "income"

    if request.method == "POST":
        # ---- ลบ Category ----
        delete_name = request.POST.get("delete_category_name")
        if delete_name:
            Category.objects.filter(
                user=user_now, category_name=delete_name, trans_type=transaction_type
            ).delete()

        # ---- เพิ่ม Category ----
        add_cat_name = request.POST.get("category_name")
        date_str = request.POST.get("date")
        if add_cat_name and not date_str:
            Category.objects.create(
                user=user_now, category_name=add_cat_name, trans_type=transaction_type
            )

        # ---- เพิ่ม Transaction Income ----
        elif add_cat_name and date_str:
            date = parse_date(date_str)  # convert string to date

            try:
                amount = float(request.POST["amount"])
                if amount <= 0:
                    messages.error(request, "Amount must be positive.")
                    return redirect(
                        reverse("transaction_income", kwargs={"user_id": user_now.id})
                    )

            except ValueError:
                messages.error(request, "Invalid amount format.")
                return redirect(
                    reverse("transaction_income", kwargs={"user_id": user_now.id})
                )

            name_category = add_cat_name
            account_name = request.POST["account"]

            # fetch category from database by user, category_name and type
            category_check = Category.objects.filter(
                user=user_now, category_name=name_category, trans_type=transaction_type
            )

            # fetch account if error then show message
            try:
                account = Account.objects.get(user=user_now, account_name=account_name)
            except ObjectDoesNotExist:
                messages.error(request, "Account not specified.")
                return redirect(
                    reverse("transaction_income", kwargs={"user_id": user_now.id})
                )

            # Check if this category exist
            if not category_check.exists():
                category = Category.objects.create(
                    user=user_now,
                    category_name=name_category,
                    trans_type=transaction_type,
                )
            else:
                category = category_check.first()

            # create transaction income model
            income = Income.objects.create(
                user=user_now,
                trans_type=transaction_type,
                date=date,
                amount=amount,
                category_trans=name_category,
                to_account=account,
            )

            account.balance += float(amount)
            account.save()

        return redirect(
            reverse("transaction_income", kwargs={"user_id": request.user.id})
        )

    categories = Category.objects.filter(user=request.user, trans_type=transaction_type)

    return render(request, "home/transaction_income.html", {"categories": categories})


@login_required(login_url="/login/")
@csrf_exempt
def transaction_expense_page(request, user_id):
    user_now = request.user
    transaction_type = "expense"

    if request.method == "POST":

        # ---- ลบ Category ----
        delete_name = request.POST.get("delete_category_name")
        if delete_name:
            Category.objects.filter(
                user=user_now, category_name=delete_name, trans_type=transaction_type
            ).delete()

        # ---- เพิ่ม Category ----
        add_cat_name = request.POST.get("category_name")
        date_str = request.POST.get("date")
        if add_cat_name and not date_str:
            Category.objects.create(
                user=user_now, category_name=add_cat_name, trans_type=transaction_type
            )

        # ---- เพิ่ม Transaction Expense ----
        elif add_cat_name and date_str:
            date = parse_date(date_str)  # convert string to date

            # Amount must be positive.
            try:
                amount = float(request.POST["amount"])
                if amount <= 0:
                    messages.error(request, "Amount must be positive.")
                    return redirect(
                        reverse("transaction_expense", kwargs={"user_id": user_now.id})
                    )

            # Invalid amount format.
            except ValueError:
                messages.error(request, "Invalid amount format.")
                return redirect(
                    reverse("transaction_expense", kwargs={"user_id": user_now.id})
                )

            name_category = add_cat_name
            account_name = request.POST["account"]

            # fetch category or create if not exist
            category = Category.objects.filter(
                user=user_now, category_name=name_category, trans_type=transaction_type
            ).first() or Category.objects.create(
                user=user_now, category_name=name_category, trans_type=transaction_type
            )

            # fetch account if error then show message
            try:
                account = Account.objects.get(user=user_now, account_name=account_name)
            except ObjectDoesNotExist:
                messages.error(request, "Account not specified.")
                return redirect(
                    reverse("transaction_expense", kwargs={"user_id": user_now.id})
                )

            # create expense
            Expense.objects.create(
                user=user_now,
                trans_type=transaction_type,
                date=date,
                amount=amount,
                category_trans=name_category,
                from_account=account,
            )

            # update account balance
            account.balance -= amount
            account.save()

        # redirect หลัง POST
        return redirect(reverse("transaction_expense", kwargs={"user_id": user_now.id}))

    categories = Category.objects.filter(user=request.user, trans_type=transaction_type)

    return render(request, "home/transaction_expense.html", {"categories": categories})


@login_required(login_url="/login/")
@csrf_exempt
def transaction_transfer_page(request, user_id):
    user_now = request.user
    transaction_type = "transfer"

    if request.method == "POST":
        # ---- ลบ Category ----
        delete_name = request.POST.get("delete_category_name")
        if delete_name:
            Category.objects.filter(
                user=user_now, category_name=delete_name, trans_type=transaction_type
            ).delete()

        # ---- เพิ่ม Category ----
        add_cat_name = request.POST.get("category_name")
        date_str = request.POST.get("date")
        if add_cat_name and not date_str:
            Category.objects.create(
                user=user_now, category_name=add_cat_name, trans_type=transaction_type
            )

        # ---- เพิ่ม Transaction Transfer ----
        elif add_cat_name and date_str:
            date = parse_date(date_str)  # convert string to date

            try:
                amount = float(request.POST["amount"])
                if amount <= 0:
                    messages.error(request, "Amount must be positive.")
                    return redirect(
                        reverse("transaction_transfer", kwargs={"user_id": user_now.id})
                    )

            # Invalid amount format.
            except ValueError:
                messages.error(request, "Invalid amount format.")
                return redirect(
                    reverse("transaction_transfer", kwargs={"user_id": user_now.id})
                )

            name_category = add_cat_name

            from_account = request.POST["from_account"]
            to_account = request.POST["to_account"]

            # fetch category from database by user, category_name and type

            category_check = Category.objects.filter(
                user=user_now, category_name=name_category, trans_type=transaction_type
            )

            # fetch accounts if error then show message
            try:
                from_account = Account.objects.get(
                    user=user_now, account_name=from_account
                )
                to_account = Account.objects.get(user=user_now, account_name=to_account)
            except ObjectDoesNotExist:
                messages.error(
                    request, "Account either not specified or does not exists."
                )
                return redirect(
                    reverse("transaction_transfer", kwargs={"user_id": user_now.id})
                )

            # Check if this category exist
            if not category_check.exists():
                category = Category.objects.create(
                    user=user_now,
                    category_name=name_category,
                    trans_type=transaction_type,
                )
            else:
                category = category_check.first()

            # create transaction income model
            expense = Expense.objects.create(
                user=user_now,
                trans_type="expense",
                date=date,
                amount=amount,
                category_trans=name_category,
                from_account=from_account,
            )

            income = Income.objects.create(
                user=user_now,
                trans_type="income",
                date=date,
                amount=amount,
                category_trans=name_category,
                to_account=to_account,
            )

            if from_account != to_account:
                from_account.balance -= float(amount)

                from_account.save()

                to_account.balance += float(amount)

                to_account.save()

            return redirect(
                reverse("transaction_transfer", kwargs={"user_id": request.user.id})
            )

    categories = Category.objects.filter(user=request.user, trans_type=transaction_type)

    return render(request, "home/transaction_transfer.html", {"categories": categories})


@login_required(login_url="/login/")
def transaction_history(request, user_id):
    """
    Transaction history with a keyword search over the category name.

    NOTE (for the security assignment): this view intentionally contains
    multiple vulnerabilities for demonstration purposes:
      * Broken Access Control / IDOR  -> it queries by the `user_id` taken
        from the URL instead of `request.user`, with no ownership check.
      * SQL Injection                 -> the `q` parameter is concatenated
        directly into a raw SQL string.
    The stored XSS vector lives in the matching template (category rendered
    with the `|safe` filter).
    """
    q = request.GET.get("q", "")

    # Raw SQL built by string concatenation. Both `user_id` (from the URL)
    # and `q` (from the query string) are attacker-controllable.
    sql = (
        "SELECT trans_id, trans_type, date, amount, category_trans "
        "FROM home_transaction "
        "WHERE user_id = " + str(user_id)
    )
    if q:
        sql += " AND category_trans LIKE '%" + q + "%'"
    sql += " ORDER BY date DESC"

    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()

    transactions = [
        {
            "id": row[0],
            "type": row[1],
            "date": row[2],
            "amount": row[3],
            "category": row[4],
        }
        for row in rows
    ]

    # Whose history we are actually showing (used to make IDOR visible in UI).
    profile_username = (
        User.objects.filter(pk=user_id)
        .values_list("username", flat=True)
        .first()
    )

    context = {
        "transactions": transactions,
        "query": q,
        "profile_user_id": user_id,
        "profile_username": profile_username,
        "executed_sql": sql,
    }
    return render(request, "home/transaction_history.html", context)


@login_required(login_url="/login/")
def stats_page(request, user_id):
    """
    View นี้จะทำหน้าที่ render หน้า HTML หลักของ Stats
    และส่งข้อมูลพื้นฐานเช่น ปีที่มี Transaction ไปให้ Template
    """
    user = request.user
    # ดึงปีทั้งหมดที่มีการทำรายการ เพื่อไปสร้างเป็นตัวเลือกใน dropdown
    # เรียงจากปีล่าสุดไปหาเก่าสุด
    years_with_transactions = Transaction.objects.filter(user=user).dates(
        "date", "year", order="DESC"
    )

    # ดึงเดือนและปีทั้งหมดที่มีรายการ expense เพื่อใช้ในหน้า Compare
    expense_months = Expense.objects.filter(user=user).dates(
        "date", "month", order="DESC"
    )

    context = {
        "years": [d.year for d in years_with_transactions],
        "expense_months": [
            {"value": d.strftime("%Y-%m"), "text": d.strftime("%B %Y")}
            for d in expense_months
        ],
    }
    return render(request, "home/stats.html", context)


@login_required
def stats_summary_api(request):
    """
    API View สำหรับส่งข้อมูล Pie Chart (Income หรือ Expense)
    รับ parameter: ?year=YYYY&month=MM&type=income
    """
    user = request.user
    year = request.GET.get("year")
    month = request.GET.get("month")
    trans_type = request.GET.get("type")  # 'income' or 'expense'

    if not all([year, month, trans_type]):
        return JsonResponse({"error": "Missing parameters"}, status=400)

    model = Income if trans_type == "income" else Expense

    # Query ข้อมูลและจัดกลุ่มตาม category
    summary = (
        model.objects.filter(user=user, date__year=year, date__month=month)
        .values("category_trans")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    overall_total = sum(item["total"] for item in summary)

    data = {
        "labels": [item["category_trans"] for item in summary],
        "values": [item["total"] for item in summary],
        "overall_total": overall_total,
    }
    return JsonResponse(data)


@login_required
def stats_yearly_api(request):
    """
    API View สำหรับส่งข้อมูล Line Chart (Statistics)
    รับ parameter: ?year=YYYY
    """
    user = request.user
    year = request.GET.get("year")

    if not year:
        return JsonResponse({"error": "Year parameter is required"}, status=400)

    income_data = []
    expense_data = []
    month_labels = [calendar.month_name[i] for i in range(1, 13)]

    for month in range(1, 13):
        income_total = (
            Income.objects.filter(
                user=user, date__year=year, date__month=month
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )
        expense_total = (
            Expense.objects.filter(
                user=user, date__year=year, date__month=month
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )
        income_data.append(income_total)
        expense_data.append(expense_total)

    data = {"labels": month_labels, "income": income_data, "expense": expense_data}
    return JsonResponse(data)


@login_required(login_url="/login/")
def settings_page(request, user_id):

    # ตรวจสอบว่ามี Profile หรือยัง ถ้าไม่ ให้สร้างทันที
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=request.user)

    # สร้าง instance ของฟอร์มต่างๆ (ใช้ 'profile' ที่เราเพิ่งสร้าง)
    u_form = UsernameUpdateForm(instance=request.user)
    p_form = ProfilePictureUpdateForm(instance=profile)
    e_form = EmailUpdateForm(instance=request.user)

    if request.method == "POST":
        # ตรวจสอบว่าปุ่มไหนถูกกด
        if "update_username" in request.POST:
            u_form = UsernameUpdateForm(request.POST, instance=request.user)
            if u_form.is_valid():
                u_form.save()
                messages.success(request, "Your username has been updated!")
                return redirect("settings", user_id=request.user.id)

        elif "update_email" in request.POST:  # <-- เพิ่มเงื่อนไขสำหรับอีเมล
            e_form = EmailUpdateForm(request.POST, instance=request.user)
            if e_form.is_valid():
                e_form.save()
                messages.success(request, "Your email has been updated!")
                return redirect("settings", user_id=request.user.id)

        elif "update_picture" in request.POST:
            p_form = ProfilePictureUpdateForm(
                request.POST, request.FILES, instance=request.user.profile
            )
            if p_form.is_valid():
                p_form.save()
                messages.success(request, "Your profile picture has been updated!")
                return redirect("settings", user_id=request.user.id)

        # ---- เปิด/ปิด Mascot ----
        elif "update_mascot" in request.POST:
            # ถ้า checkbox ถูกติ๊ก => มี key 'show_mascot' ใน POST
            profile.show_mascot = "show_mascot" in request.POST
            profile.save()
            messages.success(request, "Mascot setting has been updated!")
            return redirect("settings", user_id=request.user.id)

    context = {
        "u_form": u_form,
        "p_form": p_form,
        "e_form": e_form,
        "profile": profile,
    }
    return render(request, "home/settings.html", context)


@login_required
def delete_account_page(request):
    if request.method == "POST":
        form = AccountDeleteForm(request.POST)
        if form.is_valid():
            user = request.user
            password = form.cleaned_data["password"]
            if user.check_password(password):
                # ก่อนลบ ให้ทำการ logout เพื่อเคลียร์ session
                logout(request)
                # ทำการลบ user
                user.delete()
                messages.success(request, "Your account has been permanently deleted.")
                return redirect(
                    "login"
                )  # เปลี่ยน 'login' เป็นชื่อ URL หน้า login ของคุณใน authorized app
            else:
                messages.error(request, "Incorrect password. Account not deleted.")

    return redirect("settings")


def contact(request):
    return render(request, "home/contact.html")


@login_required(login_url="/login/")
def account_management_page(request, user_id):
    user = request.user

    # Logic สำหรับการสร้าง Account ใหม่ (POST request)
    if request.method == "POST":
        account_name = request.POST.get("account_name")
        try:
            balance = float(request.POST.get("balance", 0))
        except (ValueError, TypeError):
            messages.error(request, "Invalid balance format.")
            return redirect("account_management", user_id=user.id)

        if not account_name:
            messages.error(request, "Account name is required.")
        # ตรวจสอบว่ามีชื่อ Account นี้อยู่แล้วหรือไม่
        elif Account.objects.filter(user=user, account_name=account_name).exists():
            messages.error(
                request, f"Account with name '{account_name}' already exists."
            )
        else:
            Account.objects.create(
                user=user,
                account_name=account_name,
                balance=balance,
                type_acc="Default",
            )
            messages.success(request, f"Account '{account_name}' created successfully.")

        return redirect("account_management", user_id=user.id)

    # ดึงข้อมูล Account ทั้งหมดมาแสดง (GET request)
    accounts = Account.objects.filter(user=user).order_by("id")
    context = {"accounts": accounts}
    return render(request, "home/accounts_management.html", context)


@login_required
@require_POST  # บังคับให้ View นี้รับเฉพาะ POST request เพื่อความปลอดภัย
def update_account_api(request, account_id):
    try:
        user = request.user
        account = get_object_or_404(Account, pk=account_id, user=user)

        # เงื่อนไขป้องกันการแก้ไข 'Cash'
        if account.account_name == "Cash":
            return JsonResponse(
                {"error": "The 'Cash' account cannot be edited."}, status=403
            )

        # ดึงข้อมูลชื่อใหม่จาก request body (ที่ส่งมาจาก JavaScript)
        data = json.loads(request.body)
        new_name = data.get("account_name", "").strip()

        if not new_name:
            return JsonResponse({"error": "Account name cannot be empty."}, status=400)

        # ตรวจสอบชื่อซ้ำ
        if (
            Account.objects.filter(user=user, account_name=new_name)
            .exclude(pk=account_id)
            .exists()
        ):
            return JsonResponse(
                {"error": f"Account with name '{new_name}' already exists."}, status=400
            )

        # อัปเดตและบันทึก
        account.account_name = new_name
        account.save()

        return JsonResponse({"success": True, "new_name": account.account_name})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required(login_url="/login/")
def delete_account_view(request, user_id, account_id):
    user = request.user
    account = Account.objects.get(pk=account_id)

    if account.account_name == "Cash":
        messages.error(request, "The 'Cash' account cannot be deleted.")
    elif account.balance != 0:
        messages.error(
            request,
            f"Cannot delete '{account.account_name}' because it still has a balance. Please transfer the funds first.",
        )
    else:
        account.delete()
        messages.success(request, "Account deleted successfully.")

    return redirect("account_management", user_id=user.id)


# ----------------------------Mascot---------------------------

import random
from django.views.decorators.http import require_GET
from django.db.models import Sum
from datetime import datetime


@login_required
@require_GET
def pet_chat_api(request):
    """
    แชทสุ่มทั่วไป เ
    """
    text = ""
    return JsonResponse({"text": text})


@login_required(login_url="/login/")
@require_GET
def pet_status_api(request):

    user = request.user
    now = datetime.now()
    year, month = now.year, now.month

    # ยอดเงินรวมทุกบัญชี
    total_balance = (
        Account.objects.filter(user=user).aggregate(Sum("balance"))["balance__sum"]
        or 0.0
    )

    # รายรับ / รายจ่าย เดือนปัจจุบัน
    month_income = (
        Income.objects.filter(user=user, date__year=year, date__month=month).aggregate(
            Sum("amount")
        )["amount__sum"]
        or 0.0
    )
    month_expense = (
        Expense.objects.filter(user=user, date__year=year, date__month=month).aggregate(
            Sum("amount")
        )["amount__sum"]
        or 0.0
    )

    # % รายจ่ายต่อรายรับ
    if month_income > 0:
        expense_percentage = (month_expense / month_income) * 100
    else:
        expense_percentage = 0.0

    # อารมณ์ตาม savings rate
    if month_income > 0:
        saving_rate = ((month_income - month_expense) / month_income) * 100
    else:
        # ไม่มีรายรับ
        if month_expense == 0:
            saving_rate = 100.0  # ถือว่าโอเค ยังไม่ใช้เงิน
        else:
            saving_rate = 0.0  # ใช้เงินโดยไม่มีรายรับ

    # clamp ไว้กันค่าประหลาดที่ไม่ควรเกิดขึ้น
    saving_rate = max(-999.0, min(100.0, saving_rate))

    if month_income == 0 and month_expense == 0:
        status = "neutral"
        advice = "โอ้! ดูเหมือนว่านี้จะเป็นการ เริ่มต้นใหม่นะ เรามาลุยกันเลย 🎉"
    elif saving_rate >= 66:
        status = "happy"
        advice = "โห! เก็บเงินได้ดีมากเลย 🎉 รักษาระดับนี้ไว้นะ!"
    elif saving_rate <= 33:
        status = "danger"
        advice = "ระวังนิดนึงนะ รายจ่ายเริ่มหนักกว่าเงินที่เข้าแล้ว ⚠️"
    else:
        status = "neutral"
        advice = "ใช้จ่ายได้โอเคอยู่ แต่ลองเก็บเพิ่มอีกนิดจะดีมากเลย 😊"

    data = {
        "total_balance": round(total_balance, 2),
        "month_income": round(month_income, 2),
        "month_expense": round(month_expense, 2),
        "expense_percentage": round(expense_percentage, 2),
        "saving_rate": round(saving_rate, 2),
        "advice": advice,
        "status": status,  # happy / neutral / danger
    }
    return JsonResponse(data)
