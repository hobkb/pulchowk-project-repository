"""Turns on the pgvector extension.

Separated from the table migration so that enabling the extension, which
needs elevated privileges on some managed Postgres services, can be granted
or run independently of the ordinary schema change that follows it.
"""

from django.db import migrations
from pgvector.django import VectorExtension


class Migration(migrations.Migration):

    dependencies = [
        ("repository", "0009_alter_project_academic_level"),
    ]

    operations = [
        VectorExtension(),
    ]
