from django.contrib import admin
from .models import (
    Project,
    ProjectAsset,
    ProjectPerson,
    ProjectSection,
    Keyword,
    ProjectKeyword,
    Domain,
    ProjectDomain,
    Bookmark,
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    pass


@admin.register(ProjectAsset)
class ProjectAssetAdmin(admin.ModelAdmin):
    pass


@admin.register(ProjectPerson)
class ProjectPersonAdmin(admin.ModelAdmin):
    pass


@admin.register(ProjectSection)
class ProjectSectionAdmin(admin.ModelAdmin):
    pass


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    pass


@admin.register(ProjectKeyword)
class ProjectKeywordAdmin(admin.ModelAdmin):
    pass


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    pass


@admin.register(ProjectDomain)
class ProjectDomainAdmin(admin.ModelAdmin):
    pass


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    pass