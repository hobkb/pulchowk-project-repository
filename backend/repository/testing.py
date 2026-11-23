"""Shared helpers for repository tests.

The catalogue endpoints require a signed-in campus account, so tests that
exercise search, filters, facets or similarity -- rather than access
control -- make their requests as an ordinary reader.
"""

from rest_framework.test import APIClient

from accounts.models import User

READER_EMAIL = "reader.fixture@pcampus.edu.np"


def reader():
    user, _ = User.objects.get_or_create(email=READER_EMAIL)
    return user


def reader_client():
    """An APIClient signed in as a reader with no privileges."""
    client = APIClient()
    client.force_authenticate(user=reader())
    return client
