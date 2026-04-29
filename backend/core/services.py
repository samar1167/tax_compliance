import json
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
