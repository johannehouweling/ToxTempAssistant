# Generated migration: add persistent UUID identifier to Assay for FAIR data exports.

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("toxtempass", "0026_alter_answer_files"),
    ]

    operations = [
        migrations.AddField(
            model_name="assay",
            name="uid",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
                help_text=(
                    "Persistent identifier (UUID) for this assay, "
                    "used in FAIR data exports."
                ),
            ),
        ),
    ]
