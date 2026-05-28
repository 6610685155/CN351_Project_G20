from django.urls import path, re_path
from . import views
from django.contrib.auth import views as auth_views


urlpatterns = [
    # error handling for when no user_id is provided
    path("", views.landing_page, name="landing"),

    path("<int:user_id>/", views.home_page, name="home"),
    path("<int:user_id>/home/", views.home_page, name="home"),
    path("<int:user_id>/dashboard/", views.dashboard_today_page, name="dashboard"),
    path(
        "<int:user_id>/transaction/income/",
        views.transaction_income_page,
        name="transaction_income",
    ),
    path(
        "<int:user_id>/transaction/expense/",
        views.transaction_expense_page,
        name="transaction_expense",
    ),
    path(
        "<int:user_id>/transaction/transfer/",
        views.transaction_transfer_page,
        name="transaction_transfer",
    ),
    path("<int:user_id>/stats/", views.stats_page, name="stats"),
    path("api/stats/summary/", views.stats_summary_api, name="stats_summary_api"),
    path("api/stats/yearly/", views.stats_yearly_api, name="stats_yearly_api"),
    
    path("<int:user_id>/settings/", views.settings_page, name="settings"),
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='home/password_change.html', success_url='/settings/'), name='password_change'),
    path('delete_account/', views.delete_account_page, name='delete_account'),

    path("<int:user_id>/edit/category/", views.category_list, name="category_list"),

    path("<int:user_id>/accounts/", views.account_management_page, name="account_management"),
    path("<int:user_id>/accounts/delete/<int:account_id>/", views.delete_account_view, name="delete_account"),
    path("api/accounts/update/<int:account_id>/", views.update_account_api, name="update_account_api"),

    path("contact/", views.contact, name="contact"),
    path("api/spending/", views.spending_api, name="spending_api"),
    path("api/accounts/", views.accounts_api, name="accounts_api"),
    
    #MASCOT
    path('pet/chat/', views.pet_chat_api, name='pet_chat_api'),
    path('pet/status/', views.pet_status_api, name='pet_status_api'),

    # catch-all for any other paths without user_id
    re_path(r"^([a-zA-Z]+)/$", views.landing_page, name="landing"),
]
