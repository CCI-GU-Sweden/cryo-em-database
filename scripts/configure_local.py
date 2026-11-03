"""Create private development settings without overwriting an existing .env."""

import secrets
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    destination = root / ".env"
    if destination.exists():
        print("Existing .env kept unchanged.")
        return

    content = (root / ".env.example").read_text()
    content = content.replace(
        "DJANGO_SECRET_KEY=\n", f"DJANGO_SECRET_KEY={secrets.token_urlsafe(50)}\n"
    ).replace("POSTGRES_PASSWORD=\n", f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n")
    # Create with owner-only permissions from the start, including during writing.
    import os

    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as settings_file:
        settings_file.write(content)
    print("Created private .env with generated local secrets.")


if __name__ == "__main__":
    main()
