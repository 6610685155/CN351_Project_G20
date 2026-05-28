from django.contrib import admin
from .models import (
    Category,
    MonthReport,
    Account,
    Transaction,
    Income,
    Expense,
    Profile,
)


# -----------------------
# Category Admin
# -----------------------
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "category_name", "trans_type")
    list_filter = ("trans_type", "user")
    search_fields = ("category_name", "trans_type", "user__username")


# -----------------------
# Month Report Admin
# -----------------------
@admin.register(MonthReport)
class MonthReportAdmin(admin.ModelAdmin):
    list_display = (
        "report_id",
        "user",
        "month",
        "year",
        "income_total",
        "expense_total",
    )
    list_filter = ("year", "month", "user")
    search_fields = ("user__username",)


# -----------------------
# Account Admin
# -----------------------
@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "account_name", "type_acc", "balance")
    search_fields = ("account_name", "user__username")
    list_filter = ("type_acc", "user")
    list_editable = ("account_name", "type_acc", "balance")


# -----------------------
# Transaction Admin (Base)
# -----------------------
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "trans_id",
        "user",
        "trans_type",
        "category_trans",
        "amount",
        "date",
    )
    list_filter = ("trans_type", "user", "date")
    search_fields = ("category_trans", "user__username")


# -----------------------
# Income Admin (child of Transaction)
# -----------------------
@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ("trans_id", "user", "trans_type", "amount", "to_account", "date")
    list_filter = ("user", "to_account")
    search_fields = ("user__username",)


# -----------------------
# Expense Admin (child of Transaction)
# -----------------------
@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("trans_id", "user", "trans_type", "amount", "from_account", "date")
    list_filter = ("user", "from_account")
    search_fields = ("user__username",)


# -----------------------
# Profile Admin
# -----------------------
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "show_mascot")
    list_editable = ("show_mascot",)
    search_fields = ("user__username",)
