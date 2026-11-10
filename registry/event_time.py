"""Defaults for browser fields that represent action times as whole seconds."""

from datetime import timedelta

from django.utils import timezone


def current_action_time():
    # Avoid defaulting before a just-recorded microsecond-precision event.
    return timezone.now().replace(microsecond=0) + timedelta(seconds=1)
