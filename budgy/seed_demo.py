"""
Seed reproducible demo data for the security assignment.

Run with:
    python manage.py shell -c "exec(open('seed_demo.py').read())"

Creates two regular users (alice / bob) plus an admin, each with their own
accounts, categories and transactions so that the IDOR, SQL injection and
stored XSS demonstrations have realistic data to work against.
"""
from datetime import datetime

from django.contrib.auth.models import User
from home.models import Account, Category, Income, Expense


def reset_user(username, password, email, is_admin=False):
    User.objects.filter(username=username).delete()
    if is_admin:
        user = User.objects.create_superuser(username=username, password=password, email=email)
    else:
        user = User.objects.create_user(username=username, password=password, email=email)
    return user


def build_account(user, name, balance):
    return Account.objects.create(user=user, account_name=name, type_acc="Default", balance=balance)


def seed_user(username, password, email, rows):
    user = reset_user(username, password, email)
    cash = build_account(user, "Cash", 0.0)
    bank = build_account(user, "Bank", 0.0)
    for trans_type, category, amount in rows:
        Category.objects.get_or_create(user=user, category_name=category, trans_type=trans_type)
        if trans_type == "income":
            Income.objects.create(
                user=user, trans_type="income", date=datetime.now(),
                amount=amount, category_trans=category, to_account=bank,
            )
            bank.balance += amount
            bank.save()
        else:
            Expense.objects.create(
                user=user, trans_type="expense", date=datetime.now(),
                amount=amount, category_trans=category, from_account=cash,
            )
            cash.balance -= amount
            cash.save()
    return user


alice = seed_user(
    "alice", "Alice#2025", "alice@example.com",
    rows=[
        ("income", "Salary", 45000),
        ("expense", "Food", 1200),
        ("expense", "Transport", 600),
        ("expense", "Rent", 12000),
    ],
)

bob = seed_user(
    "bob", "Bob#2025", "bob@example.com",
    rows=[
        ("income", "Freelance", 30000),
        ("expense", "Groceries", 2500),
        ("expense", "Gaming", 1800),
    ],
)

# Admin account whose password hash is worth stealing via SQL injection.
reset_user("admin", "SuperSecret#Admin1", "admin@example.com", is_admin=True)

print("Seeded users:")
for u in User.objects.all().order_by("id"):
    print(f"  id={u.id}  username={u.username}  is_superuser={u.is_superuser}")
