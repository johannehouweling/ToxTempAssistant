from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("toxtempass", "0016_assayview"),
    ]

    operations = [
        migrations.AddField(
            model_name="assay",
            name="demo_lock",
            field=models.BooleanField(
                default=False,
                help_text="Prevent edits so this assay can be used as a read-only demo.",
            ),
        ),
        migrations.AddField(
            model_name="assay",
            name="demo_template",
            field=models.BooleanField(
                default=False,
                help_text="Marks this assay as the master template used to seed demo copies.",
            ),
        ),
        migrations.AddField(
            model_name="assay",
            name="demo_source",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="demo_copies",
                to="toxtempass.assay",
                help_text="Template assay this demo copy originated from.",
            ),
        ),
    ]
