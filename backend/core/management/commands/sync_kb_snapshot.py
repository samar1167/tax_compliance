from django.core.management.base import BaseCommand, CommandError

from core.models import KnowledgeBaseVersion
from core.services import KnowledgeBasePackageService, KnowledgeBaseService


class Command(BaseCommand):
    help = "Import the default KB package and ensure one active version exists."

    def handle(self, *args, **options):
        version = KnowledgeBasePackageService.import_package()
        if version.status == KnowledgeBaseVersion.Status.ACTIVE:
            self.stdout.write(self.style.SUCCESS(f"Knowledge base ready: {version.package_id} v{version.version}"))
            return

        active_version = (
            KnowledgeBaseVersion.objects.filter(
                module=version.module,
                assessment_year=version.assessment_year,
                status=KnowledgeBaseVersion.Status.ACTIVE,
            )
            .order_by("-activated_at", "-updated_at")
            .first()
        )

        if version.validation_errors:
            if active_version:
                self.stdout.write(
                    self.style.WARNING(
                        "Default KB package has validation errors; keeping the existing active version "
                        f"{active_version.package_id} v{active_version.version}."
                    )
                )
                self.stdout.write(f"Validation errors: {version.validation_errors}")
                return
            raise CommandError(
                "Default KB package has validation errors and no active knowledge base version is available."
            )

        if active_version and active_version.id != version.id:
            self.stdout.write(
                self.style.WARNING(
                    "Keeping the existing active knowledge base version "
                    f"{active_version.package_id} v{active_version.version}."
                )
            )
            return

        version = KnowledgeBaseService.activate_version(version.id)
        self.stdout.write(self.style.SUCCESS(f"Knowledge base ready: {version.package_id} v{version.version}"))
