from django.core.management.base import BaseCommand, CommandError

from core.services import KnowledgeBasePackageService


class Command(BaseCommand):
    help = "Import a knowledge base package directory into the system as a draft/validated version."

    def add_arguments(self, parser):
        parser.add_argument("package_path", nargs="?", default=None)

    def handle(self, *args, **options):
        try:
            version = KnowledgeBasePackageService.import_package(options["package_path"])
        except Exception as exc:  # noqa: BLE001
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {version.package_id} v{version.version} with status {version.status}"
            )
        )
        if version.validation_errors:
            self.stdout.write(f"Validation errors: {version.validation_errors}")
