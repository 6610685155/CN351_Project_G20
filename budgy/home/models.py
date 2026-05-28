from django.db import models
from django.contrib.auth.models import User


# Category Model
class Category(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category_name = models.CharField(max_length=100)
    trans_type = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["trans_type", "category_name", "user"],
                name="unique_user_type_category",
            )
        ]


# Month Report Model
class MonthReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    report_id = models.AutoField(primary_key=True)
    month = models.IntegerField()
    year = models.IntegerField()
    income_total = models.FloatField()
    expense_total = models.FloatField()


# Account Model
class Account(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    account_name = models.CharField(max_length=100)
    type_acc = models.CharField(max_length=50)
    balance = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "account_name"], name="unique_user_account"
            )
        ]


# Transaction Model
class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    trans_id = models.AutoField(primary_key=True)
    trans_type = models.CharField(max_length=50)
    date = models.DateTimeField()
    amount = models.FloatField()
    # category = models.ForeignKey(Category, on_delete=models.DO_NOTHING)
    category_trans = models.CharField(max_length=100)


# Transaction Income model
class Income(Transaction):
    to_account = models.ForeignKey(Account, on_delete=models.CASCADE)


# Transaction Expense model
class Expense(Transaction):
    from_account = models.ForeignKey(Account, on_delete=models.CASCADE)


# Mascot status on/off
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(default="default.png", upload_to="profile_pics")
    show_mascot = models.BooleanField(default=True)  # 👈 เพิ่มบรรทัดนี้

    def __str__(self):
        return f"{self.user.username} Profile"
