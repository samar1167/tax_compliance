from django.db import models


class KnowledgeBaseVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        VALIDATED = "validated", "Validated"
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    package_id = models.CharField(max_length=128)
    module = models.CharField(max_length=128)
    assessment_year = models.CharField(max_length=16)
    financial_year = models.CharField(max_length=16)
    version = models.CharField(max_length=32)
    act_version = models.CharField(max_length=128)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    manifest = models.JSONField(default=dict)
    validation_errors = models.JSONField(default=list, blank=True)
    source_path = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    last_validated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("package_id", "version")
        ordering = ("-updated_at",)

    def __str__(self) -> str:
        return f"{self.package_id} v{self.version} [{self.status}]"

    def as_summary(self) -> dict:
        return {
            "id": self.id,
            "package_id": self.package_id,
            "module": self.module,
            "assessment_year": self.assessment_year,
            "financial_year": self.financial_year,
            "version": self.version,
            "act_version": self.act_version,
            "status": self.status,
            "rule_count": self.rules.count(),
            "source_count": self.sources.count(),
            "threshold_count": self.thresholds.count(),
            "test_case_count": self.test_cases.count(),
            "bundle_count": self.rule_bundles.count(),
            "active_bundle_count": self.rule_bundles.filter(is_active=True).count(),
            "validation_error_count": len(self.validation_errors or []),
            "source_path": self.source_path,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "last_validated_at": self.last_validated_at.isoformat() if self.last_validated_at else None,
        }


class KnowledgeBaseSource(models.Model):
    kb_version = models.ForeignKey(KnowledgeBaseVersion, related_name="sources", on_delete=models.CASCADE)
    source_id = models.CharField(max_length=64)
    label = models.CharField(max_length=255)
    url = models.URLField(max_length=500)
    authority_type = models.CharField(max_length=64)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("kb_version", "source_id")
        ordering = ("source_id",)

    def __str__(self) -> str:
        return f"{self.source_id} ({self.kb_version.package_id})"


class KnowledgeBaseThreshold(models.Model):
    kb_version = models.ForeignKey(KnowledgeBaseVersion, related_name="thresholds", on_delete=models.CASCADE)
    threshold_code = models.CharField(max_length=128)
    label = models.CharField(max_length=255)
    value = models.JSONField()
    value_type = models.CharField(max_length=32, default="number")
    unit = models.CharField(max_length=32, blank=True)
    conditions = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("kb_version", "threshold_code")
        ordering = ("threshold_code",)

    def __str__(self) -> str:
        return f"{self.threshold_code}={self.value}"


class KnowledgeBaseRule(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        DRAFT = "draft", "Draft"

    kb_version = models.ForeignKey(KnowledgeBaseVersion, related_name="rules", on_delete=models.CASCADE)
    rule_id = models.CharField(max_length=64)
    module = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    version = models.CharField(max_length=32)
    effective_from_ay = models.CharField(max_length=16)
    effective_to_ay = models.CharField(max_length=16, null=True, blank=True)
    priority = models.PositiveIntegerField()
    taxpayer_scope = models.JSONField(default=dict, blank=True)
    inputs_required = models.JSONField(default=list, blank=True)
    applies_if = models.JSONField(default=dict, blank=True)
    when_json = models.JSONField()
    effect_json = models.JSONField()
    explanation_template = models.TextField(blank=True)
    source_refs = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    rule_type = models.CharField(max_length=32, default="general")
    bundle_code = models.CharField(max_length=64, blank=True)
    depends_on_rule_ids = models.JSONField(default=list, blank=True)
    blocks_rule_ids = models.JSONField(default=list, blank=True)
    requires_decision_fields = models.JSONField(default=list, blank=True)
    produces_decision_fields = models.JSONField(default=list, blank=True)

    class Meta:
        unique_together = ("kb_version", "rule_id")
        ordering = ("priority", "rule_id")

    def __str__(self) -> str:
        return self.rule_id


class KnowledgeBaseTestCase(models.Model):
    kb_version = models.ForeignKey(KnowledgeBaseVersion, related_name="test_cases", on_delete=models.CASCADE)
    case_id = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    input_payload = models.JSONField()
    expected_output = models.JSONField()
    required_active_bundle_codes = models.JSONField(default=list, blank=True)
    required_inactive_bundle_codes = models.JSONField(default=list, blank=True)
    evaluation_output = models.JSONField(default=dict, blank=True)
    passed = models.BooleanField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("kb_version", "case_id")
        ordering = ("case_id",)

    def __str__(self) -> str:
        return f"{self.case_id} ({self.kb_version.package_id})"


class KnowledgeBaseRuleBundle(models.Model):
    kb_version = models.ForeignKey(KnowledgeBaseVersion, related_name="rule_bundles", on_delete=models.CASCADE)
    bundle_code = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    depends_on_bundle_codes = models.JSONField(default=list, blank=True)
    blocks_bundle_codes = models.JSONField(default=list, blank=True)

    class Meta:
        unique_together = ("kb_version", "bundle_code")
        ordering = ("bundle_code",)

    def __str__(self) -> str:
        return f"{self.bundle_code} ({self.kb_version.package_id})"


class FilingAssessment(models.Model):
    assessment_year = models.CharField(max_length=16, default="2026-27")
    financial_year = models.CharField(max_length=16, default="2025-26")
    knowledge_base_version = models.ForeignKey(
        KnowledgeBaseVersion,
        null=True,
        blank=True,
        related_name="assessments",
        on_delete=models.SET_NULL,
    )
    input_payload = models.JSONField()
    result_payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Assessment #{self.pk} - {self.assessment_year}"
