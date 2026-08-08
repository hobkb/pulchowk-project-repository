from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from .models import Faculty, Person, Student


# Register your models here.

User = get_user_model()

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "email",
        "first_name",
        "last_name",
        "person",
        "role",
        "is_staff",
        "is_active",
    )

    ordering = ("email",)
    
    
    list_filter = (
        "role",
        "is_staff",
        "is_superuser",
        "is_active",
    )


    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "person")}),
        ("Permissions", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        ("Google", {"fields": ("google_sub",)}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "role"),
        }),
    )

    search_fields = ("email", "first_name", "last_name")

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "email",
        "department",
    )
    search_fields = ("full_name", "email")
    list_filter = ("department",)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "email",
        "department",
        "academic_level",
        "roll_number",
    )
    search_fields = ("full_name", "email", "roll_number")
    list_filter = ("department", "academic_level")


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "title",
        "designation",
        "email",
        "department",
    )
    search_fields = ("full_name", "email", "title", "designation")
    list_filter = ("department",)
