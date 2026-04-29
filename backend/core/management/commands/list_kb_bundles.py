from django.core.management.base import BaseCommand, CommandError

from core.services import KnowledgeBaseService


class Command(BaseCommand):
    help = "List rule bundles for a knowledge base version."

    def add_arguments(self, parser):
        parser.add_argument("version_id", type=int)

    def handle(self, *args, **options):
        try:
            bundles = KnowledgeBaseService.list_bundles(options["version_id"])
        except Exception as exc:  # noqa: BLE001
            raise CommandError(str(exc)) from exc

        for bundle in bundles:
            self.stdout.write(
                f"{bundle['bundle_code']}: active={bundle['is_active']} default={bundle['is_default']} rules={bundle['rule_count']}"
            )
