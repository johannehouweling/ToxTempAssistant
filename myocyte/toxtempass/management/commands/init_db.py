import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from toxtempass.views import create_questionset_from_json


class Command(BaseCommand):
    help = "Create a QuestionSet from a ToxTemp_<label>.json file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--label",
            required=True,
            help="Label matching the JSON filename: ToxTemp_<label>.json",
        )
        parser.add_argument(
            "--user-email",
            dest="user_email",
            help="Email of the user recorded as created_by. "
            "Defaults to the first superuser.",
        )

    def handle(self, *args, **options):
        label = options["label"]
        user_email = options.get("user_email")

        UserModel = get_user_model()

        if user_email:
            try:
                user = UserModel.objects.get(email=user_email)
            except UserModel.DoesNotExist:
                raise CommandError(f"User with email '{user_email}' does not exist")
        else:
            user = UserModel.objects.filter(is_superuser=True).first()
            if user is None:
                raise CommandError(
                    "No superuser found. Provide one with --user-email."
                )

        try:
            questionset = create_questionset_from_json(
                label=label, created_by=user
            )
        except FileNotFoundError as exc:
            raise CommandError(str(exc))
        except json.JSONDecodeError as exc:
            raise CommandError(f"JSON parse error: {exc}")
        except ValueError as exc:
            raise CommandError(str(exc))

        self.stdout.write(
            self.style.SUCCESS(
                f"QuestionSet '{questionset.label}' successfully created."
            )
        )
