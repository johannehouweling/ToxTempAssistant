from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("toxtempass", "0032_assay_completion_time_seconds"),
    ]

    operations = [
        migrations.AlterField(
            model_name="feedback",
            name="time_spent_seconds",
            field=models.PositiveIntegerField(
                blank=True,
                help_text=(
                    "Automatically measured active time spent on the assay page, in seconds."
                ),
                null=True,
            ),
        ),
    ]
