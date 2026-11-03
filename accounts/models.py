"""Login identities; sample ownership will live in a separate domain model."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    # Set this model before the first migration so future SSO keeps stable user IDs.
    # Django's is_staff controls admin access; it must not mean CCI membership.
    is_cci_staff = models.BooleanField(
        "CCI staff member",
        default=False,
        help_text="Allows access to the internal registry. Separate from admin access.",
    )
