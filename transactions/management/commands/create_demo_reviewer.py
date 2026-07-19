import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update the staff reviewer used for the hackathon review queue."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="eso_reviewer")
        parser.add_argument("--password")
        parser.add_argument("--email", default="reviewer@eso.ng")

    def handle(self, *args, **options):
        password = options["password"] or os.environ.get("ESO_REVIEWER_PASSWORD")
        if not password:
            raise CommandError(
                "Provide --password or set ESO_REVIEWER_PASSWORD. "
                "No default reviewer password is shipped."
            )

        user, created = User.objects.get_or_create(
            username=options["username"],
            defaults={"email": options["email"]},
        )
        user.email = options["email"]
        user.is_staff = True
        user.set_password(password)
        user.save(update_fields=["email", "is_staff", "password"])
        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} reviewer '{user.username}'."))
