from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Campus, Department, ResearchGroup, DepartmentAdmin as DepartmentAdminModel


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "location",
    ]

    search_fields = [
        "name",
        "location",
    ]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "campus",
    ]

    list_filter = [
        "campus",
    ]

    search_fields = [
        "name",
        "campus__name",
    ]


@admin.register(ResearchGroup)
class ResearchGroupAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "department",
    ]

    list_filter = [
        "department",
    ]

    search_fields = [
        "name",
        "department__name",
    ]


@admin.register(DepartmentAdminModel)
class DepartmentAdminRecordAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "faculty",
        "department",
        "designation_title",
        "is_active",
        "assigned_at",
    ]

    list_filter = [
        "department",
        "is_active",
    ]

    search_fields = [
        "faculty__full_name",
        "faculty__email",
        "department__name",
        "designation_title",
    ]