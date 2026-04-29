from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_bundle_aware_test_cases"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReturnSourceCaptureSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("assessment_year", models.CharField(default="2026-27", max_length=16)),
                ("financial_year", models.CharField(default="2025-26", max_length=16)),
                ("return_type", models.CharField(choices=[("ITR-1", "ITR-1"), ("ITR-2", "ITR-2")], max_length=16)),
                ("taxpayer_pan", models.CharField(blank=True, max_length=16)),
                ("taxpayer_name", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("ready", "Ready")], default="draft", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("-updated_at",),
            },
        ),
        migrations.CreateModel(
            name="ReturnSourceDataEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_type", models.CharField(max_length=64)),
                ("source_label", models.CharField(max_length=255)),
                ("is_mandatory", models.BooleanField(default=False)),
                (
                    "input_mode",
                    models.CharField(
                        choices=[("manual_entry", "Manual Entry"), ("test_record", "Test Record")],
                        default="manual_entry",
                        max_length=32,
                    ),
                ),
                ("test_record_id", models.CharField(blank=True, max_length=128)),
                ("source_data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="source_records",
                        to="core.returnsourcecapturesession",
                    ),
                ),
            ],
            options={
                "ordering": ("source_type",),
                "unique_together": {("session", "source_type")},
            },
        ),
    ]
