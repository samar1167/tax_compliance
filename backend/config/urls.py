from django.contrib import admin
from django.urls import path

from core import views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", views.health_check, name="health-check"),
    path("api/knowledge-base/summary/", views.knowledge_base_summary, name="knowledge-base-summary"),
    path("api/knowledge-base/versions/", views.knowledge_base_versions, name="knowledge-base-versions"),
    path(
        "api/knowledge-base/versions/<int:version_id>/",
        views.knowledge_base_version_detail,
        name="knowledge-base-version-detail",
    ),
    path(
        "api/knowledge-base/versions/<int:version_id>/required-inputs/",
        views.knowledge_base_required_inputs,
        name="knowledge-base-required-inputs",
    ),
    path("api/knowledge-base/import/", views.import_knowledge_base_package, name="knowledge-base-import"),
    path(
        "api/knowledge-base/versions/<int:version_id>/validate/",
        views.validate_knowledge_base_version,
        name="knowledge-base-version-validate",
    ),
    path(
        "api/knowledge-base/versions/<int:version_id>/activate/",
        views.activate_knowledge_base_version,
        name="knowledge-base-version-activate",
    ),
    path(
        "api/knowledge-base/versions/<int:version_id>/bundles/",
        views.knowledge_base_bundles,
        name="knowledge-base-bundles",
    ),
    path(
        "api/knowledge-base/versions/<int:version_id>/bundles/<str:bundle_code>/activate/",
        views.activate_knowledge_base_bundle,
        name="knowledge-base-bundle-activate",
    ),
    path(
        "api/knowledge-base/versions/<int:version_id>/bundles/<str:bundle_code>/deactivate/",
        views.deactivate_knowledge_base_bundle,
        name="knowledge-base-bundle-deactivate",
    ),
    path("api/assessments/evaluate/", views.evaluate_assessment, name="evaluate-assessment"),
]
