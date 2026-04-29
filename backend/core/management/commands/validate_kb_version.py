from django.core.management.base import BaseCommand, CommandError

from core.services import KnowledgeBaseService


class Command(BaseCommand):
    help = "Validate a stored knowledge base version and run its regression test cases."

    def add_arguments(self, parser):
        parser.add_argument("version_id", type=int)

    def handle(self, *args, **options):
        try:
            errors = KnowledgeBaseService.validate_version(options["version_id"])
        except Exception as exc:  # noqa: BLE001
            raise CommandError(str(exc)) from exc

        if errors:
            self.stdout.write(f"Validation errors: {errors}")
            raise CommandError("Validation failed.")
        self.stdout.write(self.style.SUCCESS("Knowledge base version validated successfully."))
