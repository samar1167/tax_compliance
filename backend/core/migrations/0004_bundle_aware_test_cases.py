from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_rule_bundles"),
    ]

    operations = [
        migrations.AddField(
            model_name="knowledgebasetestcase",
            name="required_active_bundle_codes",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="knowledgebasetestcase",
            name="required_inactive_bundle_codes",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
