from django.core.management.base import BaseCommand, CommandError

from core.services import KnowledgeBaseService


class Command(BaseCommand):
    help = "Activate a validated knowledge base version."

    def add_arguments(self, parser):
        parser.add_argument("version_id", type=int)

    def handle(self, *args, **options):
        try:
            version = KnowledgeBaseService.activate_version(options["version_id"])
        except Exception as exc:  # noqa: BLE001
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(f"Activated {version.package_id} v{version.version} for AY {version.assessment_year}")
        )
