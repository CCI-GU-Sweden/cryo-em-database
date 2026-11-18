"""Login identities; sample ownership will live in a separate domain model."""

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class RegistryUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "admin")
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        RESEARCHER = "researcher", "Researcher"
        STAFF = "staff", "Staff"
        ADMIN = "admin", "Admin"

    role = models.CharField(max_length=16, choices=Role.choices, blank=True, default="")
    objects = RegistryUserManager()
