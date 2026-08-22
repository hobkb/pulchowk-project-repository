from django.contrib import admin
from .models import (
    Project,
    ProjectAsset,
    ProjectPerson,
    ProjectSection,
    ProjectReference,
    Keyword,
    ProjectKeyword,
    Domain,
    ProjectDomain,
    Bookmark,
)


class ProjectAssetInline(admin.TabularInline):
    model = ProjectAsset
    extra = 0
    fields = ("asset_type", "file", "mime_type", "file_size", "uploaded_at")
    readonly_fields = ("uploaded_at",)


class ProjectPersonInline(admin.TabularInline):
    model = ProjectPerson
    extra = 0
    fields = ("person", "role", "display_order")
    ordering = ("display_order",)


class ProjectSectionInline(admin.StackedInline):
    model = ProjectSection
    extra = 0
    fields = ("heading", "canonical_section", "heading_level", "display_order", "page_start", "page_end", "word_count")
    readonly_fields = ("word_count",)
    ordering = ("display_order",)
    show_change_link = True


class ProjectReferenceInline(admin.TabularInline):
    model = ProjectReference
    extra = 0
    fields = ("title", "citation", "url")


class ProjectKeywordInline(admin.TabularInline):
    model = ProjectKeyword
    extra = 0
    autocomplete_fields = ("keyword",)


class ProjectDomainInline(admin.TabularInline):
    model = ProjectDomain
    extra = 0
    autocomplete_fields = ("domain",)


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "project_type",
        "academic_level",
        "status",
        "department",
        "research_group",
        "batch",
        "submitted_at",
        "created_at",
    )
    list_filter = ("status", "project_type", "academic_level", "department", "research_group", "language")
    search_fields = ("title", "abstract", "description", "github_url", "doi_url")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("department", "research_group", "created_by", "extraction_verified_by")
    inlines = [
        ProjectPersonInline,
        ProjectSectionInline,
        ProjectReferenceInline,
        ProjectAssetInline,
        ProjectKeywordInline,
        ProjectDomainInline,
    ]


@admin.register(ProjectAsset)
class ProjectAssetAdmin(admin.ModelAdmin):
    list_display = ("project", "asset_type", "mime_type", "file_size", "uploaded_at")
    list_filter = ("asset_type", "mime_type")
    search_fields = ("project__title", "file")
    readonly_fields = ("uploaded_at",)
    autocomplete_fields = ("project",)


@admin.register(ProjectPerson)
class ProjectPersonAdmin(admin.ModelAdmin):
    list_display = ("project", "person", "role", "display_order", "created_at")
    list_filter = ("role",)
    search_fields = ("project__title", "person__full_name")


@admin.register(ProjectSection)
class ProjectSectionAdmin(admin.ModelAdmin):
    list_display = ("project", "heading", "canonical_section", "heading_level", "display_order", "word_count")
    list_filter = ("canonical_section", "heading_level")
    search_fields = ("project__title", "heading", "content")


@admin.register(ProjectReference)
class ProjectReferenceAdmin(admin.ModelAdmin):
    list_display = ("project", "title", "citation", "url")
    search_fields = ("project__title", "title", "citation")


@admin.register(ProjectKeyword)
class ProjectKeywordAdmin(admin.ModelAdmin):
    list_display = ("project", "keyword")
    search_fields = ("project__title", "keyword__name")


@admin.register(ProjectDomain)
class ProjectDomainAdmin(admin.ModelAdmin):
    list_display = ("project", "domain")
    search_fields = ("project__title", "domain__name")


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "project", "created_at")
    search_fields = ("user__email", "project__title")