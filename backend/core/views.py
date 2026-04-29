import json

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import FilingAssessment, KnowledgeBaseVersion
from .services import FilingEngine, KnowledgeBasePackageService, KnowledgeBaseService


@require_GET
def health_check(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok", "service": "tax-compliance-backend"})


@require_GET
def knowledge_base_summary(request: HttpRequest) -> JsonResponse:
    summary = KnowledgeBaseService.summary(
        module=request.GET.get("module"),
        assessment_year=request.GET.get("assessment_year"),
    )
    version = KnowledgeBaseVersion.objects.get(id=summary["id"])
    summary["required_input_paths"] = FilingEngine.required_input_paths(version)
    return JsonResponse(summary)


@require_GET
def knowledge_base_versions(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"versions": KnowledgeBaseService.list_versions()})


@require_GET
def knowledge_base_version_detail(request: HttpRequest, version_id: int) -> JsonResponse:
    try:
        version = KnowledgeBaseVersion.objects.get(id=version_id)
    except KnowledgeBaseVersion.DoesNotExist:
        return JsonResponse({"error": "Knowledge base version not found."}, status=404)

    payload = version.as_summary()
    payload["validation_errors"] = version.validation_errors
    payload["manifest"] = version.manifest
    payload["sources"] = list(version.sources.values("source_id", "label", "url", "authority_type", "notes"))
    payload["thresholds"] = list(
        version.thresholds.values("threshold_code", "label", "value", "value_type", "unit", "conditions")
    )
    payload["rules"] = list(
        version.rules.values(
            "rule_id",
            "module",
            "priority",
            "status",
            "bundle_code",
            "title",
            "version",
            "effective_from_ay",
        )
    )
    payload["test_cases"] = list(
        version.test_cases.values(
            "case_id",
            "title",
            "passed",
            "last_run_at",
            "required_active_bundle_codes",
            "required_inactive_bundle_codes",
        )
    )
    payload["bundles"] = KnowledgeBaseService.list_bundles(version.id)
    payload["required_input_paths"] = FilingEngine.required_input_paths(version)
    return JsonResponse(payload)


@require_GET
def knowledge_base_required_inputs(request: HttpRequest, version_id: int) -> JsonResponse:
    try:
        version = KnowledgeBaseVersion.objects.get(id=version_id)
    except KnowledgeBaseVersion.DoesNotExist:
        return JsonResponse({"error": "Knowledge base version not found."}, status=404)

    return JsonResponse(
        {
            "version": version.as_summary(),
            "required_input_paths": FilingEngine.required_input_paths(version),
        }
    )


@csrf_exempt
@require_POST
def import_knowledge_base_package(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
        version = KnowledgeBasePackageService.import_package(payload.get("package_path"))
    except (json.JSONDecodeError, ValidationError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"version": version.as_summary(), "validation_errors": version.validation_errors}, status=201)


@csrf_exempt
@require_POST
def validate_knowledge_base_version(request: HttpRequest, version_id: int) -> JsonResponse:
    try:
        errors = KnowledgeBaseService.validate_version(version_id)
        version = KnowledgeBaseVersion.objects.get(id=version_id)
    except (ObjectDoesNotExist, ValidationError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"version": version.as_summary(), "validation_errors": errors})


@csrf_exempt
@require_POST
def activate_knowledge_base_version(request: HttpRequest, version_id: int) -> JsonResponse:
    try:
        version = KnowledgeBaseService.activate_version(version_id)
    except (ObjectDoesNotExist, ValidationError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"version": version.as_summary()})


@require_GET
def knowledge_base_bundles(request: HttpRequest, version_id: int) -> JsonResponse:
    try:
        bundles = KnowledgeBaseService.list_bundles(version_id)
    except (ObjectDoesNotExist, ValidationError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"bundles": bundles})


@csrf_exempt
@require_POST
def activate_knowledge_base_bundle(request: HttpRequest, version_id: int, bundle_code: str) -> JsonResponse:
    try:
        bundle = KnowledgeBaseService.set_bundle_active(version_id, bundle_code, True)
    except (ObjectDoesNotExist, ValidationError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"bundle_code": bundle.bundle_code, "is_active": bundle.is_active})


@csrf_exempt
@require_POST
def deactivate_knowledge_base_bundle(request: HttpRequest, version_id: int, bundle_code: str) -> JsonResponse:
    try:
        bundle = KnowledgeBaseService.set_bundle_active(version_id, bundle_code, False)
    except (ObjectDoesNotExist, ValidationError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"bundle_code": bundle.bundle_code, "is_active": bundle.is_active})


@csrf_exempt
@require_POST
def evaluate_assessment(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    result = FilingEngine.evaluate(payload)

    if result["filing_obligation"] == "insufficient_data":
        return JsonResponse({"error": "Missing required inputs.", "result": result}, status=400)

    kb_id = result["knowledge_base"]["id"]
    record = FilingAssessment.objects.create(
        assessment_year=result["knowledge_base"]["assessment_year"],
        financial_year=result["knowledge_base"]["financial_year"],
        knowledge_base_version_id=kb_id,
        input_payload=payload,
        result_payload=result,
    )

    return JsonResponse({"assessment_id": record.id, "result": result}, status=201)
