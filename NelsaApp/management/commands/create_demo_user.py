"""
Create a user you can use to test /Login/ on any environment (local DB or Render PostgreSQL).

Usage:
  python manage.py create_demo_user
  python manage.py create_demo_user --username myuser --password 'MySecure!Pass1'

Run on Render: Shell → connect to your web service → run the command against production DB.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or reset a demo login (username + password) for testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="moghamo_demo",
            help="Username to create or update (default: moghamo_demo)",
        )
        parser.add_argument(
            "--password",
            default="MoghamoDemo2026!",
            help="Password to set (default: MoghamoDemo2026!)",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        uname = options["username"].strip()
        pwd = options["password"]
        if not uname or not pwd:
            self.stderr.write(self.style.ERROR("Username and password must be non-empty."))
            return

        user, created = User.objects.get_or_create(
            username=uname,
            defaults={
                "email": f"{uname}@demo.local",
                "is_active": True,
            },
        )
        user.email = user.email or f"{uname}@demo.local"
        user.is_active = True
        user.set_password(pwd)
        user.save()

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} user.\n\n"
                f"  Open: /Login/\n"
                f"  Username: {uname}\n"
                f"  Password: {pwd}\n\n"
                "Change the password after testing if this is production."
            )
        )
