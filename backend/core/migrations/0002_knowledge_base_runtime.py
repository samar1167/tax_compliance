from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="KnowledgeBaseVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("package_id", models.CharField(max_length=128)),
                ("module", models.CharField(max_length=128)),
                ("assessment_year", models.CharField(max_length=16)),
                ("financial_year", models.CharField(max_length=16)),
                ("version", models.CharField(max_length=32)),
                ("act_version", models.CharField(max_length=128)),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Draft"), ("validated", "Validated"), ("active", "Active"), ("retired", "Retired")],
                        default="draft",
                        max_length=16,
                    ),
                ),
                ("manifest", models.JSONField(default=dict)),
                ("validation_errors", models.JSONField(blank=True, default=list)),
                ("source_path", models.CharField(max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("last_validated_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ("-updated_at",),
                "unique_together": {("package_id", "version")},
            },
        ),
        migrations.CreateModel(
            name="KnowledgeBaseThreshold",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("threshold_code", models.CharField(max_length=128)),
                ("label", models.CharField(max_length=255)),
                ("value", models.JSONField()),
                ("value_type", models.CharField(default="number", max_length=32)),
                ("unit", models.CharField(blank=True, max_length=32)),
                ("conditions", models.JSONField(blank=True, default=dict)),
                (
                    "kb_version",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="thresholds", to="core.knowledgebaseversion"),
                ),
            ],
            options={
                "ordering": ("threshold_code",),
                "unique_together": {("kb_version", "threshold_code")},
            },
        ),
        migrations.CreateModel(
            name="KnowledgeBaseTestCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("case_id", models.CharField(max_length=64)),
                ("title", models.CharField(max_length=255)),
                ("input_payload", models.JSONField()),
                ("expected_output", models.JSONField()),
                ("evaluation_output", models.JSONField(blank=True, default=dict)),
                ("passed", models.BooleanField(blank=True, null=True)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                (
                    "kb_version",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="test_cases", to="core.knowledgebaseversion"),
                ),
            ],
            options={
                "ordering": ("case_id",),
                "unique_together": {("kb_version", "case_id")},
            },
        ),
        migrations.CreateModel(
            name="KnowledgeBaseSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_id", models.CharField(max_length=64)),
                ("label", models.CharField(max_length=255)),
                ("url", models.URLField(max_length=500)),
                ("authority_type", models.CharField(max_length=64)),
                ("notes", models.TextField(blank=True)),
                (
                    "kb_version",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sources", to="core.knowledgebaseversion"),
                ),
            ],
            options={
                "ordering": ("source_id",),
                "unique_together": {("kb_version", "source_id")},
            },
        ),
        migrations.CreateModel(
            name="KnowledgeBaseRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rule_id", models.CharField(max_length=64)),
                ("module", models.CharField(max_length=64)),
                ("title", models.CharField(max_length=255)),
                ("version", models.CharField(max_length=32)),
                ("effective_from_ay", models.CharField(max_length=16)),
                ("effective_to_ay", models.CharField(blank=True, max_length=16, null=True)),
                ("priority", models.PositiveIntegerField()),
                ("taxpayer_scope", models.JSONField(blank=True, default=dict)),
                ("inputs_required", models.JSONField(blank=True, default=list)),
                ("applies_if", models.JSONField(blank=True, default=dict)),
                ("when_json", models.JSONField()),
                ("effect_json", models.JSONField()),
                ("explanation_template", models.TextField(blank=True)),
                ("source_refs", models.JSONField(blank=True, default=list)),
                (
                    "kb_version",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rules", to="core.knowledgebaseversion"),
                ),
            ],
            options={
                "ordering": ("priority", "rule_id"),
                "unique_together": {("kb_version", "rule_id")},
            },
        ),
        migrations.AddField(
            model_name="filingassessment",
            name="knowledge_base_version",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assessments", to="core.knowledgebaseversion"),
        ),
    ]
