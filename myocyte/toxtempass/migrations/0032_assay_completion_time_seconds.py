from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("toxtempass", "0031_assaytimelog"),
    ]

    operations = [
        migrations.AddField(
            model_name="assay",
            name="completion_time_seconds",
            field=models.PositiveIntegerField(
                blank=True,
                help_text=(
                    "Aggregated active time (in seconds) across all collaborators at the "
                    "moment every answer was accepted for the first time. Set automatically; "
                    "never overwritten once captured."
                ),
                null=True,
            ),
        ),
    ]
