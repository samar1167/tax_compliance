from django.core.management.base import BaseCommand

from core.services import KnowledgeBasePackageService, KnowledgeBaseService


class Command(BaseCommand):
    help = "Import the default KB package and ensure one active version exists."

    def handle(self, *args, **options):
        version = KnowledgeBasePackageService.import_package()
        if version.status != "active":
            version = KnowledgeBaseService.activate_version(version.id)
        self.stdout.write(self.style.SUCCESS(f"Knowledge base ready: {version.package_id} v{version.version}"))
