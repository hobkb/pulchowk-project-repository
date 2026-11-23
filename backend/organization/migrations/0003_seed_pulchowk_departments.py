from django.db import migrations


CAMPUS_NAME = "Pulchowk Campus"
CAMPUS_LOCATION = "Lalitpur, Nepal"

DEPARTMENTS = [
    "Department of Electronics and Computer Engineering",
    "Department of Electrical Engineering",
    "Department of Civil Engineering",
    "Department of Mechanical and Aerospace Engineering",
    "Department of Applied Sciences and Chemical Engineering",
    "Department of Architecture",
]


def seed_departments(apps, schema_editor):
    """Creates the campus and its six departments.

    The departments table was empty, so every publish fell through to
    `Department.objects.first()` -- which was None -- and each project was
    stored with department = NULL regardless of what the cover page said.

    get_or_create throughout, so this is safe to re-run and cannot disturb
    a campus or department a deployment already has.
    """
    Campus = apps.get_model("organization", "Campus")
    Department = apps.get_model("organization", "Department")

    campus, _ = Campus.objects.get_or_create(
        name=CAMPUS_NAME, defaults={"location": CAMPUS_LOCATION}
    )

    for name in DEPARTMENTS:
        Department.objects.get_or_create(name=name, campus=campus)


def unseed_departments(apps, schema_editor):
    """Removes only the departments this migration added, and only while
    nothing references them -- a department that has since been attached to
    a project is left alone rather than cascading that project away."""
    Department = apps.get_model("organization", "Department")
    Campus = apps.get_model("organization", "Campus")

    for name in DEPARTMENTS:
        Department.objects.filter(name=name, projects__isnull=True).delete()

    Campus.objects.filter(name=CAMPUS_NAME, departments__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("organization", "0002_departmentadmin"),
        # Departments are referenced by repository.Project, so the reverse
        # operation needs that table to exist to check for references.
        ("repository", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_departments, unseed_departments),
    ]
