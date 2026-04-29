from django.core.management.base import BaseCommand, CommandError

from core.services import KnowledgeBaseService


class Command(BaseCommand):
    help = "Activate a rule bundle inside a validated knowledge base version."

    def add_arguments(self, parser):
        parser.add_argument("version_id", type=int)
        parser.add_argument("bundle_code")

    def handle(self, *args, **options):
        try:
            bundle = KnowledgeBaseService.set_bundle_active(
                options["version_id"],
                options["bundle_code"],
                True,
            )
        except Exception as exc:  # noqa: BLE001
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Activated bundle {bundle.bundle_code}"))
