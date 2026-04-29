import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    FilingAssessment,
    KnowledgeBaseRule,
    KnowledgeBaseRuleBundle,
    KnowledgeBaseSource,
    KnowledgeBaseTestCase,
    KnowledgeBaseThreshold,
    KnowledgeBaseVersion,
    ReturnSourceCaptureSession,
    ReturnSourceDataEntry,
)


DEFAULT_PACKAGE_DIR = settings.REPO_ROOT / "knowledge_base" / "packages" / "ay2026_27_v1"
SUPPORTED_OPERATORS = {
    "all",
    "any",
    "not",
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "is_true",
    "is_false",
}


def load_yaml_file(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def get_value(path: str, context: dict[str, Any]) -> Any:
    current: Any = context
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def path_exists(path: str, context: dict[str, Any]) -> bool:
    current: Any = context
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return current is not None


def compare(operator: str, payload: Any, context: dict[str, Any]) -> bool:
    if operator in {"is_true", "is_false"}:
        value = get_value(payload, context)
        return bool(value) if operator == "is_true" else not bool(value)

    if operator == "all":
        return all(evaluate_predicate(item, context) for item in payload)
    if operator == "any":
        return any(evaluate_predicate(item, context) for item in payload)
    if operator == "not":
        return not evaluate_predicate(payload, context)

    left = payload["left"]
    right = payload["right"]
    left_value = get_value(left, context) if isinstance(left, str) and "." in left else left
    right_value = get_value(right, context) if isinstance(right, str) and "." in right else right

    operations = {
        "eq": lambda a, b: a == b,
        "ne": lambda a, b: a != b,
        "gt": lambda a, b: a is not None and b is not None and a > b,
        "gte": lambda a, b: a is not None and b is not None and a >= b,
        "lt": lambda a, b: a is not None and b is not None and a < b,
        "lte": lambda a, b: a is not None and b is not None and a <= b,
    }
    return operations[operator](left_value, right_value)


def evaluate_predicate(predicate: dict[str, Any], context: dict[str, Any]) -> bool:
    operator, payload = next(iter(predicate.items()))
    return compare(operator, payload, context)


def apply_decision_update(result: dict[str, Any], update: dict[str, Any]) -> None:
    path = update["path"]
    operation = update["operation"]
    value = deepcopy(update["value"])

    if operation == "set":
        result[path] = value
        return

    result.setdefault(path, [])
    if operation == "append":
        result[path].append(value)
        return
    if operation == "append_unique" and value not in result[path]:
        result[path].append(value)


class KnowledgeBasePackageService:
    @staticmethod
    def resolve_package_path(package_path: str | None = None) -> Path:
        if package_path:
            candidate = Path(package_path)
            if not candidate.is_absolute():
                candidate = settings.REPO_ROOT / package_path
            return candidate.resolve()
        return DEFAULT_PACKAGE_DIR.resolve()

    @staticmethod
    def load_package(package_path: str | None = None) -> dict[str, Any]:
        package_dir = KnowledgeBasePackageService.resolve_package_path(package_path)
        manifest_path = package_dir / "manifest.yaml"
        sources_path = package_dir / "sources.yaml"
        thresholds_path = package_dir / "thresholds.yaml"
        bundles_path = package_dir / "bundles.yaml"
        rules_dir = package_dir / "rules"
        tests_path = package_dir / "tests" / "smoke_cases.yaml"

        if not manifest_path.exists():
            raise ValidationError(f"Missing manifest.yaml in package {package_dir}.")
        if not sources_path.exists():
            raise ValidationError(f"Missing sources.yaml in package {package_dir}.")
        if not rules_dir.exists():
            raise ValidationError(f"Missing rules directory in package {package_dir}.")

        manifest = load_yaml_file(manifest_path) or {}
        sources = load_yaml_file(sources_path) or {}
        thresholds = load_yaml_file(thresholds_path) if thresholds_path.exists() else {"thresholds": []}
        bundles = load_yaml_file(bundles_path) if bundles_path.exists() else {"bundles": []}
        tests = load_yaml_file(tests_path) if tests_path.exists() else {"test_cases": []}

        rules: list[dict[str, Any]] = []
        for rule_file in sorted(rules_dir.glob("*.yaml")):
            payload = load_yaml_file(rule_file) or {}
            rules.extend(payload.get("rules", []))

        return {
            "package_dir": str(package_dir),
            "manifest": manifest,
            "sources": sources,
            "thresholds": thresholds,
            "bundles": bundles,
            "rules": rules,
            "test_cases": tests.get("test_cases", []),
        }

    @staticmethod
    def validate_package(package_data: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        manifest = package_data["manifest"]
        sources = package_data["sources"].get("sources", [])
        bundles = package_data.get("bundles", {}).get("bundles", [])
        rules = package_data["rules"]

        for field in [
            "package_id",
            "module",
            "assessment_year",
            "financial_year",
            "version",
            "act_version",
        ]:
            if not manifest.get(field):
                errors.append(f"manifest.{field} is required")

        source_ids = [item.get("source_id") for item in sources]
        if len(source_ids) != len(set(source_ids)):
            errors.append("sources.source_id values must be unique")

        known_source_ids = {item.get("source_id") for item in sources}
        known_rule_ids: set[str] = set()
        known_bundle_codes = {item.get("bundle_code") for item in bundles if item.get("bundle_code")}

        if len(known_bundle_codes) != len([item.get("bundle_code") for item in bundles if item.get("bundle_code")]):
            errors.append("bundles.bundle_code values must be unique")

        if not rules:
            errors.append("At least one rule file with rules[] is required")

        for index, rule in enumerate(rules, start=1):
            rule_id = rule.get("rule_id")
            if not rule_id:
                errors.append(f"rules[{index}] missing rule_id")
            elif rule_id in known_rule_ids:
                errors.append(f"Duplicate rule_id: {rule_id}")
            else:
                known_rule_ids.add(rule_id)

            predicate = rule.get("when")
            if not predicate:
                errors.append(f"rule {rule_id or index} missing when predicate")
            else:
                errors.extend(KnowledgeBasePackageService.validate_predicate(predicate, prefix=f"rule {rule_id}"))

            source_refs = rule.get("source_refs", [])
            if not source_refs:
                errors.append(f"rule {rule_id or index} must reference at least one source")
            for source_ref in source_refs:
                if source_ref.get("source_id") not in known_source_ids:
                    errors.append(
                        f"rule {rule_id or index} references unknown source_id {source_ref.get('source_id')}"
                    )

            bundle_code = rule.get("bundle_code", "")
            if bundle_code and bundle_code not in known_bundle_codes:
                errors.append(f"rule {rule_id or index} references unknown bundle_code {bundle_code}")

        return errors

    @staticmethod
    def validate_predicate(predicate: dict[str, Any], prefix: str) -> list[str]:
        errors: list[str] = []
        if not isinstance(predicate, dict) or len(predicate) != 1:
            return [f"{prefix} contains invalid predicate node"]

        operator, payload = next(iter(predicate.items()))
        if operator not in SUPPORTED_OPERATORS:
            return [f"{prefix} uses unsupported operator {operator}"]

        if operator in {"all", "any"}:
            if not isinstance(payload, list) or not payload:
                return [f"{prefix} {operator} requires a non-empty list"]
            for child in payload:
                errors.extend(KnowledgeBasePackageService.validate_predicate(child, prefix))
            return errors

        if operator == "not":
            return KnowledgeBasePackageService.validate_predicate(payload, prefix)

        if operator in {"is_true", "is_false"}:
            if not isinstance(payload, str):
                errors.append(f"{prefix} {operator} requires a fact path string")
            return errors

        if not isinstance(payload, dict) or "left" not in payload or "right" not in payload:
            errors.append(f"{prefix} {operator} requires left and right")
        return errors

    @staticmethod
    @transaction.atomic
    def import_package(package_path: str | None = None) -> KnowledgeBaseVersion:
        package_data = KnowledgeBasePackageService.load_package(package_path)
        errors = KnowledgeBasePackageService.validate_package(package_data)
        manifest = package_data["manifest"]

        version, _ = KnowledgeBaseVersion.objects.update_or_create(
            package_id=manifest["package_id"],
            version=manifest["version"],
            defaults={
                "module": manifest["module"],
                "assessment_year": manifest["assessment_year"],
                "financial_year": manifest["financial_year"],
                "act_version": manifest["act_version"],
                "status": KnowledgeBaseVersion.Status.DRAFT,
                "manifest": manifest,
                "source_path": package_data["package_dir"],
                "notes": manifest.get("notes", ""),
                "validation_errors": errors,
            },
        )

        version.sources.all().delete()
        version.thresholds.all().delete()
        version.rule_bundles.all().delete()
        version.rules.all().delete()
        version.test_cases.all().delete()

        for source in package_data["sources"].get("sources", []):
            KnowledgeBaseSource.objects.create(
                kb_version=version,
                source_id=source["source_id"],
                label=source["label"],
                url=source["url"],
                authority_type=source["authority_type"],
                notes=source.get("notes", ""),
            )

        for threshold in package_data["thresholds"].get("thresholds", []):
            KnowledgeBaseThreshold.objects.create(
                kb_version=version,
                threshold_code=threshold["threshold_code"],
                label=threshold["label"],
                value=threshold["value"],
                value_type=threshold.get("value_type", "number"),
                unit=threshold.get("unit", ""),
                conditions=threshold.get("conditions", {}),
            )

        for bundle in package_data.get("bundles", {}).get("bundles", []):
            KnowledgeBaseRuleBundle.objects.create(
                kb_version=version,
                bundle_code=bundle["bundle_code"],
                title=bundle["title"],
                description=bundle.get("description", ""),
                is_default=bool(bundle.get("is_default", False)),
                is_active=bool(bundle.get("is_active", False)),
                depends_on_bundle_codes=bundle.get("depends_on_bundle_codes", []),
                blocks_bundle_codes=bundle.get("blocks_bundle_codes", []),
            )

        for rule in package_data["rules"]:
            KnowledgeBaseRule.objects.create(
                kb_version=version,
                rule_id=rule["rule_id"],
                module=rule["module"],
                title=rule["title"],
                version=rule["version"],
                effective_from_ay=rule["effective_from_ay"],
                effective_to_ay=rule.get("effective_to_ay"),
                priority=rule["priority"],
                taxpayer_scope=rule.get("taxpayer_scope", {}),
                inputs_required=rule.get("inputs_required", []),
                applies_if=rule.get("applies_if", {}),
                when_json=rule["when"],
                effect_json=rule["effect"],
                explanation_template=rule.get("explanation_template", ""),
                source_refs=rule.get("source_refs", []),
                status=rule.get("status", KnowledgeBaseRule.Status.ACTIVE),
                rule_type=rule.get("rule_type", "general"),
                bundle_code=rule.get("bundle_code", ""),
                depends_on_rule_ids=rule.get("depends_on_rule_ids", []),
                blocks_rule_ids=rule.get("blocks_rule_ids", []),
                requires_decision_fields=rule.get("requires_decision_fields", []),
                produces_decision_fields=rule.get("produces_decision_fields", []),
            )

        for test_case in package_data["test_cases"]:
            KnowledgeBaseTestCase.objects.create(
                kb_version=version,
                case_id=test_case["case_id"],
                title=test_case["title"],
                input_payload=test_case["input_payload"],
                expected_output=test_case["expected_output"],
                required_active_bundle_codes=test_case.get("required_active_bundle_codes", []),
                required_inactive_bundle_codes=test_case.get("required_inactive_bundle_codes", []),
            )

        if not errors:
            version.status = KnowledgeBaseVersion.Status.VALIDATED
            version.last_validated_at = timezone.now()
            version.save(update_fields=["status", "last_validated_at", "updated_at", "validation_errors"])

        return version


class KnowledgeBaseService:
    @staticmethod
    def get_active_version(module: str | None = None, assessment_year: str | None = None) -> KnowledgeBaseVersion:
        queryset = KnowledgeBaseVersion.objects.filter(status=KnowledgeBaseVersion.Status.ACTIVE)
        if module:
            queryset = queryset.filter(module=module)
        if assessment_year:
            queryset = queryset.filter(assessment_year=assessment_year)

        version = queryset.order_by("-activated_at", "-updated_at").first()
        if version:
            return version

        version = KnowledgeBasePackageService.import_package()
        KnowledgeBaseService.activate_version(version.id)
        return version

    @staticmethod
    def activate_version(version_id: int) -> KnowledgeBaseVersion:
        version = KnowledgeBaseVersion.objects.get(id=version_id)
        errors = KnowledgeBaseService.validate_version(version.id)
        if errors:
            raise ValidationError("Cannot activate a knowledge base version with validation errors.")

        with transaction.atomic():
            KnowledgeBaseVersion.objects.filter(
                module=version.module,
                assessment_year=version.assessment_year,
                status=KnowledgeBaseVersion.Status.ACTIVE,
            ).exclude(id=version.id).update(status=KnowledgeBaseVersion.Status.RETIRED)

            version.status = KnowledgeBaseVersion.Status.ACTIVE
            version.activated_at = timezone.now()
            version.last_validated_at = timezone.now()
            version.save(update_fields=["status", "activated_at", "last_validated_at", "updated_at"])
        return version

    @staticmethod
    def validate_version(version_id: int) -> list[str]:
        version = KnowledgeBaseVersion.objects.get(id=version_id)
        previous_status = version.status
        package_data = {
            "manifest": version.manifest,
            "sources": {
                "sources": list(
                    version.sources.values("source_id", "label", "url", "authority_type", "notes")
                )
            },
            "bundles": {
                "bundles": list(
                    version.rule_bundles.values(
                        "bundle_code",
                        "title",
                        "description",
                        "is_default",
                        "is_active",
                        "depends_on_bundle_codes",
                        "blocks_bundle_codes",
                    )
                )
            },
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "module": rule.module,
                    "title": rule.title,
                    "version": rule.version,
                    "effective_from_ay": rule.effective_from_ay,
                    "effective_to_ay": rule.effective_to_ay,
                    "priority": rule.priority,
                    "taxpayer_scope": rule.taxpayer_scope,
                    "inputs_required": rule.inputs_required,
                    "applies_if": rule.applies_if,
                    "when": rule.when_json,
                    "effect": rule.effect_json,
                    "explanation_template": rule.explanation_template,
                    "source_refs": rule.source_refs,
                    "status": rule.status,
                    "rule_type": rule.rule_type,
                    "bundle_code": rule.bundle_code,
                    "depends_on_rule_ids": rule.depends_on_rule_ids,
                    "blocks_rule_ids": rule.blocks_rule_ids,
                    "requires_decision_fields": rule.requires_decision_fields,
                    "produces_decision_fields": rule.produces_decision_fields,
                }
                for rule in version.rules.order_by("priority", "rule_id")
            ],
        }

        errors = KnowledgeBasePackageService.validate_package(package_data)
        errors.extend(KnowledgeBaseService.validate_effective_rule_graph(version))
        regression_errors = KnowledgeBaseService.run_test_cases(version)
        errors.extend(regression_errors)

        version.validation_errors = errors
        version.last_validated_at = timezone.now()
        if errors:
            version.status = KnowledgeBaseVersion.Status.DRAFT
        elif previous_status == KnowledgeBaseVersion.Status.ACTIVE:
            version.status = KnowledgeBaseVersion.Status.ACTIVE
        else:
            version.status = KnowledgeBaseVersion.Status.VALIDATED
        version.save(update_fields=["validation_errors", "last_validated_at", "status", "updated_at"])
        return errors

    @staticmethod
    def get_active_bundle_codes(version: KnowledgeBaseVersion) -> set[str]:
        return set(
            version.rule_bundles.filter(is_active=True).values_list("bundle_code", flat=True)
        )

    @staticmethod
    def get_effective_rules(version: KnowledgeBaseVersion) -> list[KnowledgeBaseRule]:
        active_bundle_codes = KnowledgeBaseService.get_active_bundle_codes(version)
        effective_rules: list[KnowledgeBaseRule] = []

        for rule in version.rules.order_by("priority", "rule_id"):
            if rule.status == KnowledgeBaseRule.Status.INACTIVE:
                continue
            if rule.status == KnowledgeBaseRule.Status.DRAFT:
                continue
            if rule.bundle_code and rule.bundle_code not in active_bundle_codes:
                continue
            effective_rules.append(rule)
        return effective_rules

    @staticmethod
    def validate_effective_rule_graph(version: KnowledgeBaseVersion) -> list[str]:
        errors: list[str] = []
        bundles = {bundle.bundle_code: bundle for bundle in version.rule_bundles.all()}
        active_bundle_codes = KnowledgeBaseService.get_active_bundle_codes(version)

        for bundle in bundles.values():
            if not bundle.is_active:
                continue
            for dependency in bundle.depends_on_bundle_codes:
                if dependency not in active_bundle_codes:
                    errors.append(
                        f"bundle {bundle.bundle_code} depends on inactive bundle {dependency}"
                    )
            for blocked in bundle.blocks_bundle_codes:
                if blocked in active_bundle_codes:
                    errors.append(
                        f"bundle {bundle.bundle_code} blocks active bundle {blocked}"
                    )

        effective_rules = KnowledgeBaseService.get_effective_rules(version)
        effective_rule_ids = {rule.rule_id for rule in effective_rules}
        produced_fields: set[str] = set()

        for rule in effective_rules:
            produced_fields.update(rule.produces_decision_fields or [])

        for rule in effective_rules:
            for dependency in rule.depends_on_rule_ids:
                if dependency not in effective_rule_ids:
                    errors.append(f"rule {rule.rule_id} depends on inactive or missing rule {dependency}")
            for blocked in rule.blocks_rule_ids:
                if blocked in effective_rule_ids:
                    errors.append(f"rule {rule.rule_id} blocks simultaneously active rule {blocked}")
            for required_field in rule.requires_decision_fields:
                if required_field not in produced_fields and not required_field.startswith("decision.itr"):
                    errors.append(f"rule {rule.rule_id} requires missing decision field {required_field}")

        return errors

    @staticmethod
    def list_bundles(version_id: int) -> list[dict[str, Any]]:
        version = KnowledgeBaseVersion.objects.get(id=version_id)
        return [
            {
                "id": bundle.id,
                "bundle_code": bundle.bundle_code,
                "title": bundle.title,
                "description": bundle.description,
                "is_default": bundle.is_default,
                "is_active": bundle.is_active,
                "depends_on_bundle_codes": bundle.depends_on_bundle_codes,
                "blocks_bundle_codes": bundle.blocks_bundle_codes,
                "rule_count": version.rules.filter(bundle_code=bundle.bundle_code).count(),
            }
            for bundle in version.rule_bundles.order_by("bundle_code")
        ]

    @staticmethod
    def set_bundle_active(version_id: int, bundle_code: str, is_active: bool) -> KnowledgeBaseRuleBundle:
        version = KnowledgeBaseVersion.objects.get(id=version_id)
        bundle = version.rule_bundles.get(bundle_code=bundle_code)
        previous = bundle.is_active
        bundle.is_active = is_active
        bundle.save(update_fields=["is_active"])
        errors = KnowledgeBaseService.validate_version(version_id)
        if errors:
            bundle.is_active = previous
            bundle.save(update_fields=["is_active"])
            KnowledgeBaseService.validate_version(version_id)
            raise ValidationError(f"Bundle toggle blocked by validation errors: {errors}")
        return bundle

    @staticmethod
    def run_test_cases(version: KnowledgeBaseVersion) -> list[str]:
        errors: list[str] = []
        active_bundle_codes = KnowledgeBaseService.get_active_bundle_codes(version)
        for test_case in version.test_cases.all().order_by("case_id"):
            required_active = set(test_case.required_active_bundle_codes or [])
            required_inactive = set(test_case.required_inactive_bundle_codes or [])

            if not required_active.issubset(active_bundle_codes):
                test_case.passed = None
                test_case.evaluation_output = {"skipped": True, "reason": "required bundles not active"}
                test_case.last_run_at = timezone.now()
                test_case.save(update_fields=["evaluation_output", "passed", "last_run_at"])
                continue

            if required_inactive.intersection(active_bundle_codes):
                test_case.passed = None
                test_case.evaluation_output = {"skipped": True, "reason": "required bundles must stay inactive"}
                test_case.last_run_at = timezone.now()
                test_case.save(update_fields=["evaluation_output", "passed", "last_run_at"])
                continue

            result = FilingEngine.evaluate(test_case.input_payload, kb_version=version)
            test_case.evaluation_output = result

            expected_form = test_case.expected_output.get("recommended_form")
            expected_obligation = test_case.expected_output.get("filing_obligation")
            passed = True

            if expected_form is not None and result.get("recommended_form") != expected_form:
                errors.append(
                    f"test_case {test_case.case_id} expected recommended_form={expected_form}, got {result.get('recommended_form')}"
                )
                passed = False

            if expected_obligation is not None and result.get("filing_obligation") != expected_obligation:
                errors.append(
                    f"test_case {test_case.case_id} expected filing_obligation={expected_obligation}, got {result.get('filing_obligation')}"
                )
                passed = False

            expected_reason_codes = test_case.expected_output.get("filing_obligation_reasons_contains", [])
            for reason_code in expected_reason_codes:
                if reason_code not in result.get("filing_obligation_reasons", []):
                    errors.append(
                        f"test_case {test_case.case_id} expected filing reason {reason_code} not found"
                    )
                    passed = False

            expected_itr1_exclusions = test_case.expected_output.get("itr1_ineligibility_reasons_contains", [])
            for reason_code in expected_itr1_exclusions:
                if reason_code not in result.get("itr1_ineligibility_reasons", []):
                    errors.append(
                        f"test_case {test_case.case_id} expected ITR-1 exclusion {reason_code} not found"
                    )
                    passed = False

            test_case.passed = passed
            test_case.last_run_at = timezone.now()
            test_case.save(update_fields=["evaluation_output", "passed", "last_run_at"])
        return errors

    @staticmethod
    def summary(module: str | None = None, assessment_year: str | None = None) -> dict[str, Any]:
        version = KnowledgeBaseService.get_active_version(module=module, assessment_year=assessment_year)
        return version.as_summary()

    @staticmethod
    def list_versions() -> list[dict[str, Any]]:
        return [version.as_summary() for version in KnowledgeBaseVersion.objects.order_by("-updated_at")]


class FilingEngine:
    @staticmethod
    def default_result() -> dict[str, Any]:
        return {
            "filing_obligation": "not_required",
            "filing_obligation_reasons": [],
            "validation_errors": [],
            "eligible_forms": [],
            "ineligible_forms": [],
            "itr1_eligible": False,
            "itr2_eligible": True,
            "itr1_ineligibility_reasons": [],
            "itr2_ineligibility_reasons": [],
            "recommended_form": None,
            "decision_trace": [],
            "outside_scope": False,
            "next_expected_forms": [],
        }

    @staticmethod
    def required_input_paths(kb_version: KnowledgeBaseVersion) -> list[str]:
        paths: list[str] = []
        for rule in KnowledgeBaseService.get_effective_rules(kb_version):
            for input_path in rule.inputs_required or []:
                if input_path.startswith("decision."):
                    continue
                if input_path not in paths:
                    paths.append(input_path)
        return sorted(paths)

    @staticmethod
    def validate_payload(payload: dict[str, Any], kb_version: KnowledgeBaseVersion) -> list[str]:
        missing_paths = []
        for path in FilingEngine.required_input_paths(kb_version):
            if not path_exists(path, payload):
                missing_paths.append(path)
        return missing_paths

    @staticmethod
    def normalize_payload(payload: dict[str, Any], kb_version: KnowledgeBaseVersion | None = None) -> dict[str, Any]:
        profile = payload.get("profile", {})
        income = payload.get("income", {})
        specified = payload.get("specified_triggers", {})
        context = payload.get("context", {})
        thresholds = {
            threshold.threshold_code: threshold.value
            for threshold in (kb_version.thresholds.all() if kb_version else [])
        }

        return {
            "profile": {
                "person_type": profile.get("person_type", "individual"),
                "residential_status": profile.get("residential_status", "resident_ordinary"),
                "age_on_previous_year_end": int(profile.get("age_on_previous_year_end", 30)),
                "is_director_in_company": bool(profile.get("is_director_in_company", False)),
                "held_unlisted_equity_shares": bool(profile.get("held_unlisted_equity_shares", False)),
                "has_foreign_asset": bool(profile.get("has_foreign_asset", False)),
                "has_foreign_signing_authority": bool(profile.get("has_foreign_signing_authority", False)),
                "has_foreign_source_income": bool(profile.get("has_foreign_source_income", False)),
                "has_deferred_esop_tax": bool(profile.get("has_deferred_esop_tax", False)),
                "tds_under_194n": bool(profile.get("tds_under_194n", False)),
                "is_beneficiary_of_foreign_asset": bool(profile.get("is_beneficiary_of_foreign_asset", False)),
            },
            "income": {
                "total_income": float(income.get("total_income", 0)),
                "total_income_before_specified_exemptions_and_chapter_via": float(
                    income.get("total_income_before_specified_exemptions_and_chapter_via", income.get("total_income", 0))
                ),
                "salary_income": float(income.get("salary_income", 0)),
                "house_property_count": int(income.get("house_property_count", 1)),
                "agricultural_income": float(income.get("agricultural_income", 0)),
                "business_or_profession_income": float(income.get("business_or_profession_income", 0)),
                "business_turnover": float(income.get("business_turnover", 0)),
                "professional_receipts": float(income.get("professional_receipts", 0)),
                "short_term_capital_gains": float(income.get("short_term_capital_gains", 0)),
                "ltcg_112a_amount": float(income.get("ltcg_112a_amount", 0)),
                "other_capital_gains_amount": float(income.get("other_capital_gains_amount", 0)),
                "brought_forward_loss_exists": bool(income.get("brought_forward_loss_exists", False)),
                "loss_to_carry_forward_exists": bool(income.get("loss_to_carry_forward_exists", False)),
                "partnership_firm_interest_salary_bonus_commission": float(
                    income.get("partnership_firm_interest_salary_bonus_commission", 0)
                ),
            },
            "specified_triggers": {
                "current_account_deposits": float(specified.get("current_account_deposits", 0)),
                "foreign_travel_expenditure": float(specified.get("foreign_travel_expenditure", 0)),
                "electricity_expenditure": float(specified.get("electricity_expenditure", 0)),
                "aggregate_tds_tcs": float(specified.get("aggregate_tds_tcs", 0)),
                "savings_bank_deposits": float(specified.get("savings_bank_deposits", 0)),
            },
            "context": {
                "basic_exemption_limit": float(
                    context.get("basic_exemption_limit", thresholds.get("BASIC_EXEMPTION_LIMIT_DEFAULT", 300000))
                ),
                "assessment_year": context.get(
                    "assessment_year",
                    kb_version.assessment_year if kb_version else "2026-27",
                ),
                "financial_year": context.get(
                    "financial_year",
                    kb_version.financial_year if kb_version else "2025-26",
                ),
                "thresholds": thresholds,
            },
        }

    @staticmethod
    def evaluate(payload: dict[str, Any], kb_version: KnowledgeBaseVersion | None = None) -> dict[str, Any]:
        selected_version = kb_version
        if selected_version is None:
            request_context = payload.get("context", {})
            selected_version = KnowledgeBaseService.get_active_version(
                module=request_context.get("module"),
                assessment_year=request_context.get("assessment_year"),
            )

        missing_paths = FilingEngine.validate_payload(payload, selected_version)
        if missing_paths:
            result = FilingEngine.default_result()
            result["filing_obligation"] = "insufficient_data"
            result["validation_errors"] = [
                {
                    "code": "MISSING_REQUIRED_INPUT",
                    "path": path,
                    "message": f"Missing required input: {path}",
                }
                for path in missing_paths
            ]
            result["knowledge_base"] = selected_version.as_summary()
            result["knowledge_base"]["active_bundles"] = sorted(
                KnowledgeBaseService.get_active_bundle_codes(selected_version)
            )
            return result

        facts = FilingEngine.normalize_payload(payload, kb_version=selected_version)
        result = FilingEngine.default_result()

        rules = KnowledgeBaseService.get_effective_rules(selected_version)
        for rule in rules:
            evaluation_context = {**facts, "decision": result}
            if evaluate_predicate(rule.when_json, evaluation_context):
                for update in rule.effect_json["decision_updates"]:
                    apply_decision_update(result, update)
                result["decision_trace"].append(rule.rule_id)

        if result["itr1_eligible"] and "ITR-1" not in result["eligible_forms"]:
            result["eligible_forms"].append("ITR-1")

        if result["itr1_eligible"] and result["recommended_form"] is None:
            result["recommended_form"] = "ITR-1"

        if facts["income"]["business_or_profession_income"] > 0:
            result["outside_scope"] = True
            result["next_expected_forms"] = ["ITR-3", "ITR-4"]
            if result["recommended_form"] == "ITR-2":
                result["recommended_form"] = None

        result["knowledge_base"] = selected_version.as_summary()
        result["knowledge_base"]["active_bundles"] = sorted(KnowledgeBaseService.get_active_bundle_codes(selected_version))
        result["normalized_facts"] = facts
        return result

    @staticmethod
    def dump_pretty(data: dict[str, Any]) -> str:
        return json.dumps(data, indent=2, sort_keys=True)


class ReturnPreparationService:
    COMMON_FIELD_SPECS = [
        {
            "field_code": "residential_status",
            "label": "Residential status",
            "target_path": "profile.residential_status",
            "sources": [
                {"source_type": "declared_data", "path": "profile.residential_status"},
                {"source_type": "personal_info", "path": "residential_status"},
            ],
            "required": True,
            "authoritative_source_types": ["personal_info"],
            "final_source_precedence": ["personal_info", "declared_data"],
        },
        {
            "field_code": "salary_income",
            "label": "Salary income",
            "target_path": "income.salary_income",
            "sources": [
                {"source_type": "declared_data", "path": "income.salary_income"},
                {"source_type": "form16", "path": "salary_income"},
                {"source_type": "ais", "path": "salary_income"},
            ],
            "required": False,
            "authoritative_source_types": ["form16", "ais"],
            "final_source_precedence": ["form16", "ais", "declared_data"],
            "tolerance": 1.0,
        },
        {
            "field_code": "total_income",
            "label": "Total income",
            "target_path": "income.total_income",
            "sources": [
                {"source_type": "declared_data", "path": "income.total_income"},
                {"source_type": "form16", "path": "total_income"},
                {"source_type": "ais", "path": "total_income"},
            ],
            "required": True,
            "authoritative_source_types": ["form16", "ais"],
            "final_source_precedence": ["form16", "ais", "declared_data"],
            "tolerance": 1.0,
        },
        {
            "field_code": "total_income_before_adjustments",
            "label": "Total income before deductions/exemptions",
            "target_path": "income.total_income_before_specified_exemptions_and_chapter_via",
            "sources": [
                {
                    "source_type": "declared_data",
                    "path": "income.total_income_before_specified_exemptions_and_chapter_via",
                },
                {"source_type": "form16", "path": "total_income_before_specified_exemptions_and_chapter_via"},
                {"source_type": "ais", "path": "total_income_before_specified_exemptions_and_chapter_via"},
            ],
            "required": True,
            "authoritative_source_types": ["form16", "ais"],
            "final_source_precedence": ["form16", "ais", "declared_data"],
            "tolerance": 1.0,
        },
        {
            "field_code": "aggregate_tds_tcs",
            "label": "Aggregate TDS/TCS",
            "target_path": "specified_triggers.aggregate_tds_tcs",
            "sources": [
                {"source_type": "declared_data", "path": "specified_triggers.aggregate_tds_tcs"},
                {"source_type": "form26as", "path": "aggregate_tds_tcs"},
                {"source_type": "ais", "path": "aggregate_tds_tcs"},
            ],
            "required": False,
            "authoritative_source_types": ["form26as", "ais"],
            "final_source_precedence": ["form26as", "ais", "declared_data"],
            "tolerance": 1.0,
        },
        {
            "field_code": "house_property_count",
            "label": "House property count",
            "target_path": "income.house_property_count",
            "sources": [
                {"source_type": "declared_data", "path": "income.house_property_count"},
                {"source_type": "house_property_schedule", "path": "house_property_count"},
            ],
            "required": True,
            "authoritative_source_types": ["house_property_schedule"],
            "final_source_precedence": ["house_property_schedule", "declared_data"],
        },
        {
            "field_code": "agricultural_income",
            "label": "Agricultural income",
            "target_path": "income.agricultural_income",
            "sources": [
                {"source_type": "declared_data", "path": "income.agricultural_income"},
                {"source_type": "ais", "path": "agricultural_income"},
            ],
            "required": False,
            "authoritative_source_types": ["ais"],
            "final_source_precedence": ["ais", "declared_data"],
            "tolerance": 1.0,
        },
        {
            "field_code": "foreign_asset_flag",
            "label": "Foreign asset flag",
            "target_path": "profile.has_foreign_asset",
            "sources": [
                {"source_type": "declared_data", "path": "profile.has_foreign_asset"},
                {"source_type": "personal_info", "path": "has_foreign_asset"},
            ],
            "required": False,
            "authoritative_source_types": ["personal_info"],
            "final_source_precedence": ["personal_info", "declared_data"],
        },
        {
            "field_code": "foreign_signing_authority_flag",
            "label": "Foreign signing authority flag",
            "target_path": "profile.has_foreign_signing_authority",
            "sources": [
                {"source_type": "declared_data", "path": "profile.has_foreign_signing_authority"},
                {"source_type": "personal_info", "path": "has_foreign_signing_authority"},
            ],
            "required": False,
            "authoritative_source_types": ["personal_info"],
            "final_source_precedence": ["personal_info", "declared_data"],
        },
        {
            "field_code": "foreign_source_income_flag",
            "label": "Foreign source income flag",
            "target_path": "profile.has_foreign_source_income",
            "sources": [
                {"source_type": "declared_data", "path": "profile.has_foreign_source_income"},
                {"source_type": "personal_info", "path": "has_foreign_source_income"},
                {"source_type": "ais", "path": "has_foreign_source_income"},
            ],
            "required": False,
            "authoritative_source_types": ["personal_info", "ais"],
            "final_source_precedence": ["personal_info", "ais", "declared_data"],
        },
        {
            "field_code": "director_flag",
            "label": "Director in company flag",
            "target_path": "profile.is_director_in_company",
            "sources": [
                {"source_type": "declared_data", "path": "profile.is_director_in_company"},
                {"source_type": "personal_info", "path": "is_director_in_company"},
            ],
            "required": False,
            "authoritative_source_types": ["personal_info"],
            "final_source_precedence": ["personal_info", "declared_data"],
        },
        {
            "field_code": "unlisted_shares_flag",
            "label": "Held unlisted equity shares flag",
            "target_path": "profile.held_unlisted_equity_shares",
            "sources": [
                {"source_type": "declared_data", "path": "profile.held_unlisted_equity_shares"},
                {"source_type": "personal_info", "path": "held_unlisted_equity_shares"},
            ],
            "required": False,
            "authoritative_source_types": ["personal_info"],
            "final_source_precedence": ["personal_info", "declared_data"],
        },
    ]
    ITR2_FIELD_SPECS = [
        {
            "field_code": "short_term_capital_gains",
            "label": "Short-term capital gains",
            "target_path": "income.short_term_capital_gains",
            "sources": [
                {"source_type": "declared_data", "path": "income.short_term_capital_gains"},
                {"source_type": "capital_gains_statement", "path": "short_term_capital_gains"},
                {"source_type": "ais", "path": "short_term_capital_gains"},
            ],
            "required": False,
            "authoritative_source_types": ["capital_gains_statement", "ais"],
            "final_source_precedence": ["capital_gains_statement", "ais", "declared_data"],
            "tolerance": 1.0,
        },
        {
            "field_code": "ltcg_112a_amount",
            "label": "LTCG under section 112A",
            "target_path": "income.ltcg_112a_amount",
            "sources": [
                {"source_type": "declared_data", "path": "income.ltcg_112a_amount"},
                {"source_type": "capital_gains_statement", "path": "ltcg_112a_amount"},
                {"source_type": "ais", "path": "ltcg_112a_amount"},
            ],
            "required": False,
            "authoritative_source_types": ["capital_gains_statement", "ais"],
            "final_source_precedence": ["capital_gains_statement", "ais", "declared_data"],
            "tolerance": 1.0,
        },
        {
            "field_code": "other_capital_gains_amount",
            "label": "Other capital gains",
            "target_path": "income.other_capital_gains_amount",
            "sources": [
                {"source_type": "declared_data", "path": "income.other_capital_gains_amount"},
                {"source_type": "capital_gains_statement", "path": "other_capital_gains_amount"},
                {"source_type": "ais", "path": "other_capital_gains_amount"},
            ],
            "required": False,
            "authoritative_source_types": ["capital_gains_statement", "ais"],
            "final_source_precedence": ["capital_gains_statement", "ais", "declared_data"],
            "tolerance": 1.0,
        },
    ]

    @staticmethod
    def source_label(source_type: str) -> str:
        labels = {
            "declared_data": "Declared form data",
            "personal_info": "Personal info document",
            "form16": "Form 16",
            "form26as": "Form 26AS",
            "ais": "AIS/TIS",
            "capital_gains_statement": "Capital gains statement",
            "house_property_schedule": "House property schedule",
        }
        return labels.get(source_type, source_type.replace("_", " ").title())

    @staticmethod
    def build_field_specs(return_type: str) -> list[dict[str, Any]]:
        specs = list(ReturnPreparationService.COMMON_FIELD_SPECS)
        if return_type == "ITR-2":
            specs.extend(ReturnPreparationService.ITR2_FIELD_SPECS)
        return specs

    @staticmethod
    def expected_document_types(return_type: str, declared_data: dict[str, Any], documents_by_type: dict[str, Any]) -> list[str]:
        expected = {"personal_info", "ais", "form26as"}
        salary_income = get_value("income.salary_income", declared_data) or 0
        capital_gains = sum(
            float(get_value(path, declared_data) or 0)
            for path in [
                "income.short_term_capital_gains",
                "income.ltcg_112a_amount",
                "income.other_capital_gains_amount",
            ]
        )

        if salary_income > 0 or "form16" in documents_by_type:
            expected.add("form16")
        if return_type == "ITR-2" or capital_gains > 0 or "capital_gains_statement" in documents_by_type:
            expected.add("capital_gains_statement")
        if get_value("income.house_property_count", declared_data) not in (None, 0, 1) or "house_property_schedule" in documents_by_type:
            expected.add("house_property_schedule")
        return sorted(expected)

    @staticmethod
    def _aggregate_document_value(documents: list[dict[str, Any]], path: str) -> Any:
        values = [get_value(path, document.get("data", {})) for document in documents]
        values = [value for value in values if value is not None]
        if not values:
            return None
        if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            return float(sum(values))
        if all(isinstance(value, bool) for value in values):
            return any(values)
        if len({json.dumps(value, sort_keys=True) for value in values}) == 1:
            return values[0]
        return values[0]

    @staticmethod
    def _values_match(left: Any, right: Any, tolerance: float | None = None) -> bool:
        if left is None or right is None:
            return False
        if isinstance(left, bool) or isinstance(right, bool):
            return left is right
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            if tolerance is None:
                return float(left) == float(right)
            return math.isclose(float(left), float(right), abs_tol=tolerance)
        return left == right

    @staticmethod
    def _set_nested_value(target: dict[str, Any], path: str, value: Any) -> None:
        current = target
        parts = path.split(".")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value

    @staticmethod
    def _default_validation_payload(context: dict[str, Any]) -> dict[str, Any]:
        return {
            "context": {
                "assessment_year": context.get("assessment_year", "2026-27"),
                "financial_year": context.get("financial_year", "2025-26"),
                "basic_exemption_limit": context.get("basic_exemption_limit", 300000),
            },
            "profile": {
                "person_type": "individual",
                "residential_status": "resident_ordinary",
                "age_on_previous_year_end": 30,
                "is_director_in_company": False,
                "held_unlisted_equity_shares": False,
                "has_foreign_asset": False,
                "has_foreign_signing_authority": False,
                "has_foreign_source_income": False,
                "has_deferred_esop_tax": False,
                "tds_under_194n": False,
                "is_beneficiary_of_foreign_asset": False,
            },
            "income": {
                "total_income": 0,
                "total_income_before_specified_exemptions_and_chapter_via": 0,
                "salary_income": 0,
                "house_property_count": 1,
                "agricultural_income": 0,
                "business_or_profession_income": 0,
                "business_turnover": 0,
                "professional_receipts": 0,
                "short_term_capital_gains": 0,
                "ltcg_112a_amount": 0,
                "other_capital_gains_amount": 0,
                "brought_forward_loss_exists": False,
                "loss_to_carry_forward_exists": False,
                "partnership_firm_interest_salary_bonus_commission": 0,
            },
            "specified_triggers": {
                "current_account_deposits": 0,
                "foreign_travel_expenditure": 0,
                "electricity_expenditure": 0,
                "aggregate_tds_tcs": 0,
                "savings_bank_deposits": 0,
            },
        }

    @staticmethod
    def _derive_missing_values(validation_payload: dict[str, Any]) -> None:
        income = validation_payload["income"]
        if not income.get("total_income"):
            income["total_income"] = (
                float(income.get("salary_income", 0))
                + float(income.get("business_or_profession_income", 0))
                + float(income.get("short_term_capital_gains", 0))
                + float(income.get("ltcg_112a_amount", 0))
                + float(income.get("other_capital_gains_amount", 0))
                + float(income.get("agricultural_income", 0))
            )
        if not income.get("total_income_before_specified_exemptions_and_chapter_via"):
            income["total_income_before_specified_exemptions_and_chapter_via"] = income["total_income"]

    @staticmethod
    def prepare(payload: dict[str, Any]) -> dict[str, Any]:
        return_type = (payload.get("return_type") or "ITR-1").upper()
        if return_type not in {"ITR-1", "ITR-2"}:
            raise ValidationError("return_type must be either ITR-1 or ITR-2.")

        declared_data = payload.get("declared_data", {})
        if not isinstance(declared_data, dict):
            raise ValidationError("declared_data must be an object.")

        documents = payload.get("documents", [])
        if not isinstance(documents, list):
            raise ValidationError("documents must be a list.")

        documents_by_type: dict[str, list[dict[str, Any]]] = {}
        for document in documents:
            if not isinstance(document, dict):
                raise ValidationError("Each document must be an object.")
            document_type = document.get("document_type")
            document_data = document.get("data")
            if not document_type or not isinstance(document_type, str):
                raise ValidationError("Each document must include a document_type string.")
            if not isinstance(document_data, dict):
                raise ValidationError(f"Document {document_type} must include a data object.")
            documents_by_type.setdefault(document_type, []).append(document)

        expected_document_types = ReturnPreparationService.expected_document_types(
            return_type,
            declared_data,
            documents_by_type,
        )
        flags: list[dict[str, Any]] = []
        for document_type in expected_document_types:
            if document_type not in documents_by_type:
                flags.append(
                    {
                        "code": "MISSING_DOCUMENT",
                        "severity": "error",
                        "document_type": document_type,
                        "message": f"Missing expected document: {ReturnPreparationService.source_label(document_type)}.",
                    }
                )

        validation_payload = ReturnPreparationService._default_validation_payload(payload.get("context", {}))
        for section in ("context", "profile", "income", "specified_triggers"):
            if isinstance(declared_data.get(section), dict):
                validation_payload[section].update(declared_data[section])

        field_comparisons: list[dict[str, Any]] = []
        for spec in ReturnPreparationService.build_field_specs(return_type):
            sources_observed = []
            for source in spec["sources"]:
                source_type = source["source_type"]
                if source_type == "declared_data":
                    value = get_value(source["path"], declared_data)
                else:
                    value = ReturnPreparationService._aggregate_document_value(
                        documents_by_type.get(source_type, []),
                        source["path"],
                    )
                if value is not None:
                    sources_observed.append(
                        {
                            "source_type": source_type,
                            "source_label": ReturnPreparationService.source_label(source_type),
                            "path": source["path"],
                            "value": value,
                        }
                    )

            authoritative_values = [
                source
                for source in sources_observed
                if source["source_type"] in spec.get("authoritative_source_types", [])
            ]
            declared_value = next(
                (source["value"] for source in sources_observed if source["source_type"] == "declared_data"),
                None,
            )

            status = "missing"
            if sources_observed:
                status = "matched"

            tolerance = spec.get("tolerance")
            if len(authoritative_values) > 1:
                base_value = authoritative_values[0]["value"]
                if any(
                    not ReturnPreparationService._values_match(base_value, item["value"], tolerance)
                    for item in authoritative_values[1:]
                ):
                    status = "mismatch"
                    flags.append(
                        {
                            "code": "DOCUMENT_DATA_MISMATCH",
                            "severity": "error",
                            "field_code": spec["field_code"],
                            "message": f"{spec['label']} does not match across uploaded documents.",
                        }
                    )
            if status != "mismatch" and declared_value is not None and authoritative_values:
                base_value = authoritative_values[0]["value"]
                if not ReturnPreparationService._values_match(base_value, declared_value, tolerance):
                    status = "declared_mismatch"
                    flags.append(
                        {
                            "code": "DECLARED_DATA_MISMATCH",
                            "severity": "warning",
                            "field_code": spec["field_code"],
                            "message": f"{spec['label']} in declared data does not match uploaded documents.",
                        }
                    )

            final_value = None
            final_source_type = None
            for source_type in spec["final_source_precedence"]:
                match = next((item for item in sources_observed if item["source_type"] == source_type), None)
                if match is not None:
                    final_value = match["value"]
                    final_source_type = source_type
                    break

            if final_value is not None:
                ReturnPreparationService._set_nested_value(validation_payload, spec["target_path"], final_value)
            elif spec.get("required"):
                flags.append(
                    {
                        "code": "MISSING_REQUIRED_FIELD_EVIDENCE",
                        "severity": "error",
                        "field_code": spec["field_code"],
                        "message": f"No declared or document-backed value found for {spec['label']}.",
                    }
                )

            field_comparisons.append(
                {
                    "field_code": spec["field_code"],
                    "label": spec["label"],
                    "target_path": spec["target_path"],
                    "status": status,
                    "final_value": final_value,
                    "final_source_type": final_source_type,
                    "sources_observed": sources_observed,
                }
            )

        ReturnPreparationService._derive_missing_values(validation_payload)

        evaluation_result = FilingEngine.evaluate(validation_payload)
        blocking_flags = [flag for flag in flags if flag["severity"] == "error"]

        return {
            "return_type": return_type,
            "documents_received": sorted(documents_by_type.keys()),
            "expected_document_types": expected_document_types,
            "ready_for_validation": not blocking_flags and evaluation_result["filing_obligation"] != "insufficient_data",
            "flags": flags,
            "field_comparisons": field_comparisons,
            "prepared_return_data": {
                "profile": validation_payload["profile"],
                "income": validation_payload["income"],
                "specified_triggers": validation_payload["specified_triggers"],
            },
            "validation_payload": validation_payload,
            "validation_result": evaluation_result,
        }


SOURCE_TYPE_CATALOG = {
    "ITR-1": [
        {
            "source_type": "personal_info",
            "label": "Personal Info",
            "mandatory": True,
            "description": "Identity, PAN, name, and residency-related declarations.",
            "capture_fields": ["pan", "name", "residential_status"],
        },
        {
            "source_type": "form16",
            "label": "Form 16",
            "mandatory": True,
            "description": "Employer-issued salary and TDS summary.",
            "capture_fields": [
                "pan",
                "salary_income",
                "total_income",
                "total_income_before_specified_exemptions_and_chapter_via",
            ],
        },
        {
            "source_type": "form26as",
            "label": "Form 26AS",
            "mandatory": True,
            "description": "Tax credit statement for TDS/TCS and taxes paid.",
            "capture_fields": ["pan", "aggregate_tds_tcs"],
        },
        {
            "source_type": "ais",
            "label": "AIS/TIS",
            "mandatory": True,
            "description": "Annual information statement for cross-checking reported income.",
            "capture_fields": ["pan", "salary_income", "total_income"],
        },
        {
            "source_type": "house_property_schedule",
            "label": "House Property Schedule",
            "mandatory": False,
            "description": "Property count and related house property facts when relevant.",
            "capture_fields": ["pan", "house_property_count"],
        },
    ],
    "ITR-2": [
        {
            "source_type": "personal_info",
            "label": "Personal Info",
            "mandatory": True,
            "description": "Identity, PAN, name, and residency-related declarations.",
            "capture_fields": ["pan", "name", "residential_status"],
        },
        {
            "source_type": "form26as",
            "label": "Form 26AS",
            "mandatory": True,
            "description": "Tax credit statement for TDS/TCS and taxes paid.",
            "capture_fields": ["pan", "aggregate_tds_tcs"],
        },
        {
            "source_type": "ais",
            "label": "AIS/TIS",
            "mandatory": True,
            "description": "Annual information statement for cross-checking income heads.",
            "capture_fields": ["pan", "total_income"],
        },
        {
            "source_type": "form16",
            "label": "Form 16",
            "mandatory": False,
            "description": "Employer-issued salary and TDS summary when salary income exists.",
            "capture_fields": [
                "pan",
                "salary_income",
                "total_income",
                "total_income_before_specified_exemptions_and_chapter_via",
            ],
        },
        {
            "source_type": "capital_gains_statement",
            "label": "Capital Gains Statement",
            "mandatory": False,
            "description": "Broker or registrar statement for capital gains details.",
            "capture_fields": [
                "pan",
                "short_term_capital_gains",
                "ltcg_112a_amount",
                "other_capital_gains_amount",
            ],
        },
        {
            "source_type": "house_property_schedule",
            "label": "House Property Schedule",
            "mandatory": False,
            "description": "Property count and related house property facts when relevant.",
            "capture_fields": ["pan", "house_property_count"],
        },
    ],
}

SOURCE_TYPE_TEST_RECORDS = {
    "personal_info": [
        {
            "test_record_id": "pi_itr1_standard",
            "label": "ITR-1 resident taxpayer",
            "return_types": ["ITR-1", "ITR-2"],
            "data": {
                "pan": "ABCDE1234F",
                "name": "Aarav Sharma",
                "residential_status": "resident_ordinary",
                "has_foreign_asset": False,
                "has_foreign_signing_authority": False,
                "has_foreign_source_income": False,
            },
        },
        {
            "test_record_id": "pi_itr2_foreign_asset",
            "label": "ITR-2 foreign asset profile",
            "return_types": ["ITR-2"],
            "data": {
                "pan": "ABCDE1234F",
                "name": "Aarav Sharma",
                "residential_status": "resident_ordinary",
                "has_foreign_asset": True,
                "has_foreign_signing_authority": False,
                "has_foreign_source_income": True,
            },
        },
    ],
    "form16": [
        {
            "test_record_id": "f16_itr1_salary",
            "label": "ITR-1 salary Form 16",
            "return_types": ["ITR-1", "ITR-2"],
            "data": {
                "pan": "ABCDE1234F",
                "salary_income": 1200000,
                "total_income": 1200000,
                "total_income_before_specified_exemptions_and_chapter_via": 1200000,
            },
        },
        {
            "test_record_id": "f16_itr1_mid_salary",
            "label": "ITR-1 mid-salary Form 16",
            "return_types": ["ITR-1", "ITR-2"],
            "data": {
                "pan": "ABCDE1234F",
                "salary_income": 600000,
                "total_income": 600000,
                "total_income_before_specified_exemptions_and_chapter_via": 600000,
            },
        },
    ],
    "form26as": [
        {
            "test_record_id": "26as_standard",
            "label": "Standard Form 26AS",
            "return_types": ["ITR-1", "ITR-2"],
            "data": {
                "pan": "ABCDE1234F",
                "aggregate_tds_tcs": 45000,
            },
        },
        {
            "test_record_id": "26as_mid",
            "label": "Mid-value Form 26AS",
            "return_types": ["ITR-1", "ITR-2"],
            "data": {
                "pan": "ABCDE1234F",
                "aggregate_tds_tcs": 22000,
            },
        },
    ],
    "ais": [
        {
            "test_record_id": "ais_itr1_clean",
            "label": "AIS aligned to ITR-1",
            "return_types": ["ITR-1", "ITR-2"],
            "data": {
                "pan": "ABCDE1234F",
                "salary_income": 1200000,
                "total_income": 1200000,
                "short_term_capital_gains": 0,
            },
        },
        {
            "test_record_id": "ais_itr2_capital_gains",
            "label": "AIS with capital gains",
            "return_types": ["ITR-2"],
            "data": {
                "pan": "ABCDE1234F",
                "salary_income": 900000,
                "total_income": 1100000,
                "short_term_capital_gains": 200000,
            },
        },
    ],
    "capital_gains_statement": [
        {
            "test_record_id": "cg_stmt_standard",
            "label": "Capital gains statement",
            "return_types": ["ITR-2"],
            "data": {
                "pan": "ABCDE1234F",
                "short_term_capital_gains": 200000,
                "ltcg_112a_amount": 0,
                "other_capital_gains_amount": 0,
            },
        }
    ],
    "house_property_schedule": [
        {
            "test_record_id": "hp_single_property",
            "label": "Single house property",
            "return_types": ["ITR-1", "ITR-2"],
            "data": {
                "pan": "ABCDE1234F",
                "house_property_count": 1,
            },
        },
        {
            "test_record_id": "hp_multiple_properties",
            "label": "Multiple house properties",
            "return_types": ["ITR-2"],
            "data": {
                "pan": "ABCDE1234F",
                "house_property_count": 2,
            },
        },
    ],
}


class ReturnSourceCaptureService:
    @staticmethod
    def get_source_types(return_type: str) -> list[dict[str, Any]]:
        normalized = return_type.upper()
        if normalized not in SOURCE_TYPE_CATALOG:
            raise ValidationError("return_type must be either ITR-1 or ITR-2.")
        return deepcopy(SOURCE_TYPE_CATALOG[normalized])

    @staticmethod
    def get_source_type_definition(return_type: str, source_type: str) -> dict[str, Any]:
        for definition in ReturnSourceCaptureService.get_source_types(return_type):
            if definition["source_type"] == source_type:
                return definition
        raise ValidationError(f"source_type {source_type} is not applicable for {return_type}.")

    @staticmethod
    def list_test_records(return_type: str, source_type: str | None = None) -> list[dict[str, Any]]:
        ReturnSourceCaptureService.get_source_types(return_type)
        records: list[dict[str, Any]] = []
        for current_source_type, entries in SOURCE_TYPE_TEST_RECORDS.items():
            if source_type and current_source_type != source_type:
                continue
            for entry in entries:
                if return_type.upper() not in entry["return_types"]:
                    continue
                records.append(
                    {
                        "source_type": current_source_type,
                        "test_record_id": entry["test_record_id"],
                        "label": entry["label"],
                        "data": deepcopy(entry["data"]),
                    }
                )
        return records

    @staticmethod
    def get_test_record(return_type: str, source_type: str, test_record_id: str) -> dict[str, Any]:
        for record in ReturnSourceCaptureService.list_test_records(return_type, source_type=source_type):
            if record["test_record_id"] == test_record_id:
                return record
        raise ValidationError(f"Unknown test record {test_record_id} for {source_type} and {return_type}.")

    @staticmethod
    def create_session(payload: dict[str, Any]) -> ReturnSourceCaptureSession:
        return_type = (payload.get("return_type") or "").upper()
        ReturnSourceCaptureService.get_source_types(return_type)
        return ReturnSourceCaptureSession.objects.create(
            return_type=return_type,
            assessment_year=payload.get("assessment_year", "2026-27"),
            financial_year=payload.get("financial_year", "2025-26"),
            taxpayer_pan=payload.get("taxpayer_pan", ""),
            taxpayer_name=payload.get("taxpayer_name", ""),
        )

    @staticmethod
    def validate_source_data(definition: dict[str, Any], source_data: dict[str, Any]) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        for field in definition["capture_fields"]:
            if source_data.get(field) in (None, ""):
                errors.append(
                    {
                        "code": "MISSING_SOURCE_FIELD",
                        "field": field,
                        "message": f"{definition['label']} requires field {field}.",
                    }
                )
        return errors

    @staticmethod
    @transaction.atomic
    def save_source_data(session_id: int, payload: dict[str, Any]) -> ReturnSourceDataEntry:
        session = ReturnSourceCaptureSession.objects.get(id=session_id)
        source_type = payload.get("source_type")
        if not source_type:
            raise ValidationError("source_type is required.")

        definition = ReturnSourceCaptureService.get_source_type_definition(session.return_type, source_type)
        source_data = payload.get("source_data")
        test_record_id = payload.get("test_record_id", "")

        if test_record_id:
            record = ReturnSourceCaptureService.get_test_record(session.return_type, source_type, test_record_id)
            source_data = record["data"]

        if not isinstance(source_data, dict):
            raise ValidationError("source_data must be an object.")

        errors = ReturnSourceCaptureService.validate_source_data(definition, source_data)
        if errors:
            raise ValidationError(json.dumps(errors))

        entry, _ = ReturnSourceDataEntry.objects.update_or_create(
            session=session,
            source_type=source_type,
            defaults={
                "source_label": definition["label"],
                "is_mandatory": definition["mandatory"],
                "input_mode": ReturnSourceDataEntry.InputMode.TEST_RECORD if test_record_id else ReturnSourceDataEntry.InputMode.MANUAL,
                "test_record_id": test_record_id,
                "source_data": source_data,
            },
        )

        ReturnSourceCaptureService.refresh_session_status(session)
        return entry

    @staticmethod
    def refresh_session_status(session: ReturnSourceCaptureSession) -> ReturnSourceCaptureSession:
        saved_source_types = set(session.source_records.values_list("source_type", flat=True))
        mandatory_types = {
            definition["source_type"]
            for definition in ReturnSourceCaptureService.get_source_types(session.return_type)
            if definition["mandatory"]
        }
        session.status = (
            ReturnSourceCaptureSession.Status.READY
            if mandatory_types.issubset(saved_source_types)
            else ReturnSourceCaptureSession.Status.DRAFT
        )
        session.save(update_fields=["status", "updated_at"])
        return session

    @staticmethod
    def serialize_session(session: ReturnSourceCaptureSession) -> dict[str, Any]:
        definitions = ReturnSourceCaptureService.get_source_types(session.return_type)
        saved_records = {record.source_type: record for record in session.source_records.all()}
        mandatory_pending = []
        source_types = []

        for definition in definitions:
            saved_record = saved_records.get(definition["source_type"])
            if definition["mandatory"] and saved_record is None:
                mandatory_pending.append(definition["source_type"])
            source_types.append(
                {
                    **definition,
                    "captured": saved_record is not None,
                    "captured_record": {
                        "id": saved_record.id,
                        "input_mode": saved_record.input_mode,
                        "test_record_id": saved_record.test_record_id,
                        "source_data": saved_record.source_data,
                        "updated_at": saved_record.updated_at.isoformat(),
                    }
                    if saved_record
                    else None,
                }
            )

        return {
            "id": session.id,
            "return_type": session.return_type,
            "assessment_year": session.assessment_year,
            "financial_year": session.financial_year,
            "taxpayer_pan": session.taxpayer_pan,
            "taxpayer_name": session.taxpayer_name,
            "status": session.status,
            "mandatory_source_types_pending": mandatory_pending,
            "source_types": source_types,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }
