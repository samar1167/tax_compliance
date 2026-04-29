from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_return_source_capture"),
    ]

    operations = [
        migrations.DeleteModel(
            name="KnowledgeBaseSnapshot",
        ),
    ]
