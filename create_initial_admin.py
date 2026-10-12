
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

if not username or not email or not password:
    raise RuntimeError("Admin environment variables are missing.")

if User.objects.filter(username=username).exists():
    print("Initial admin already exists; skipping creation.")
else:
    User.objects.create_superuser(
        username=username,
        email=email,
        password=password,
    )
    print("Initial admin created successfully.")
