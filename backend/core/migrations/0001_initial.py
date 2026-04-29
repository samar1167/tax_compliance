from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="KnowledgeBaseSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("assessment_year", models.CharField(max_length=16, unique=True)),
                ("financial_year", models.CharField(max_length=16)),
                ("act_version", models.CharField(max_length=128)),
                ("source_count", models.PositiveIntegerField(default=0)),
                ("rule_count", models.PositiveIntegerField(default=0)),
                ("source_file", models.CharField(max_length=255)),
                ("synced_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="FilingAssessment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("assessment_year", models.CharField(default="2026-27", max_length=16)),
                ("financial_year", models.CharField(default="2025-26", max_length=16)),
                ("input_payload", models.JSONField()),
                ("result_payload", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
