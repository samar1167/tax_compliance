from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_knowledge_base_runtime"),
    ]

    operations = [
        migrations.AddField(
            model_name="knowledgebaserule",
            name="blocks_rule_ids",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="knowledgebaserule",
            name="bundle_code",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="knowledgebaserule",
            name="depends_on_rule_ids",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="knowledgebaserule",
            name="produces_decision_fields",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="knowledgebaserule",
            name="requires_decision_fields",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="knowledgebaserule",
            name="rule_type",
            field=models.CharField(default="general", max_length=32),
        ),
        migrations.AddField(
            model_name="knowledgebaserule",
            name="status",
            field=models.CharField(
                choices=[("active", "Active"), ("inactive", "Inactive"), ("draft", "Draft")],
                default="active",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="KnowledgeBaseRuleBundle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bundle_code", models.CharField(max_length=64)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=False)),
                ("depends_on_bundle_codes", models.JSONField(blank=True, default=list)),
                ("blocks_bundle_codes", models.JSONField(blank=True, default=list)),
                (
                    "kb_version",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rule_bundles", to="core.knowledgebaseversion"),
                ),
            ],
            options={
                "ordering": ("bundle_code",),
                "unique_together": {("kb_version", "bundle_code")},
            },
        ),
    ]
