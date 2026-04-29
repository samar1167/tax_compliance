from django.contrib import admin

from .models import (
    FilingAssessment,
    KnowledgeBaseRule,
    KnowledgeBaseRuleBundle,
    KnowledgeBaseSource,
    KnowledgeBaseTestCase,
    KnowledgeBaseThreshold,
    KnowledgeBaseVersion,
)


class KnowledgeBaseSourceInline(admin.TabularInline):
    model = KnowledgeBaseSource
    extra = 0


class KnowledgeBaseThresholdInline(admin.TabularInline):
    model = KnowledgeBaseThreshold
    extra = 0


class KnowledgeBaseRuleInline(admin.TabularInline):
    model = KnowledgeBaseRule
    extra = 0
    fields = ("rule_id", "module", "priority", "status", "bundle_code", "title")
    readonly_fields = ("rule_id", "module", "priority", "status", "bundle_code", "title")
    show_change_link = True


class KnowledgeBaseTestCaseInline(admin.TabularInline):
    model = KnowledgeBaseTestCase
    extra = 0
    fields = ("case_id", "title", "passed", "last_run_at")
    readonly_fields = ("case_id", "title", "passed", "last_run_at")
    show_change_link = True


class KnowledgeBaseRuleBundleInline(admin.TabularInline):
    model = KnowledgeBaseRuleBundle
    extra = 0


@admin.register(KnowledgeBaseVersion)
class KnowledgeBaseVersionAdmin(admin.ModelAdmin):
    list_display = (
        "package_id",
        "version",
        "module",
        "assessment_year",
        "status",
        "activated_at",
        "last_validated_at",
    )
    list_filter = ("status", "module", "assessment_year")
    readonly_fields = ("created_at", "updated_at", "activated_at", "last_validated_at")
    search_fields = ("package_id", "module", "assessment_year", "financial_year")
    inlines = [
        KnowledgeBaseRuleBundleInline,
        KnowledgeBaseSourceInline,
        KnowledgeBaseThresholdInline,
        KnowledgeBaseRuleInline,
        KnowledgeBaseTestCaseInline,
    ]


@admin.register(KnowledgeBaseRule)
class KnowledgeBaseRuleAdmin(admin.ModelAdmin):
    list_display = ("rule_id", "kb_version", "module", "priority", "status", "bundle_code", "title")
    list_filter = ("module", "status", "bundle_code", "kb_version__assessment_year")
    search_fields = ("rule_id", "title", "kb_version__package_id")


@admin.register(KnowledgeBaseRuleBundle)
class KnowledgeBaseRuleBundleAdmin(admin.ModelAdmin):
    list_display = ("bundle_code", "kb_version", "is_default", "is_active", "title")
    list_filter = ("is_default", "is_active", "kb_version__assessment_year")
    search_fields = ("bundle_code", "title", "kb_version__package_id")


@admin.register(KnowledgeBaseSource)
class KnowledgeBaseSourceAdmin(admin.ModelAdmin):
    list_display = ("source_id", "kb_version", "authority_type", "label")
    list_filter = ("authority_type", "kb_version__assessment_year")
    search_fields = ("source_id", "label", "url")


@admin.register(KnowledgeBaseThreshold)
class KnowledgeBaseThresholdAdmin(admin.ModelAdmin):
    list_display = ("threshold_code", "kb_version", "value", "unit")
    list_filter = ("kb_version__assessment_year",)
    search_fields = ("threshold_code", "label")


@admin.register(KnowledgeBaseTestCase)
class KnowledgeBaseTestCaseAdmin(admin.ModelAdmin):
    list_display = ("case_id", "kb_version", "passed", "last_run_at")
    list_filter = ("passed", "kb_version__assessment_year")
    search_fields = ("case_id", "title")


@admin.register(FilingAssessment)
class FilingAssessmentAdmin(admin.ModelAdmin):
    list_display = ("id", "assessment_year", "financial_year", "knowledge_base_version", "created_at")
    readonly_fields = ("created_at",)
    search_fields = ("assessment_year", "financial_year")
