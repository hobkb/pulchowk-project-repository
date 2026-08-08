from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("repository", "0005_alter_project_demo_url_alter_project_doi_url_and_more"),
        ("organization", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="project",
            name="department",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="projects",
                to="organization.department",
            ),
        ),
    ]
