from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin


class UserAdmin(BaseUserAdmin):
    # What columns show in the user list
    list_display = ("username", "email")

    # Remove fields you don't want to show
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("email",)}),
    )

    # Fields for adding a new user
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
    )

    # Search by username or email
    search_fields = ("username", "email")
    ordering = ("username",)


# Unregister default admin
admin.site.unregister(User)
admin.site.unregister(Group)

# Register your custom one
admin.site.register(User, UserAdmin)
