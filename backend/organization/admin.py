from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Campus, Department, ResearchGroup


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